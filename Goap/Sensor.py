import subprocess
import inspect
import json
import boto3


class SensorError(Exception):
    """ Sensor's Error base class """
    pass


class SensorResponse:
    """ SensorReturn is a class for represent the agent's sensor's return """

    def __init__(self, **kwargs):
        """

        :param kwargs: expects respose as dict argument and parse aws http response or shell Popen.response
        """
        self.return_code = None
        self.output = None
        self.error = None
        self.sensor_response = kwargs.get('response', None)
        self.popen_communicate_timeout = 10
        self.popen_parsed_response = None
        self.json_parsed_response = None
        if type(self.sensor_response) == dict:
            self.__parse_aws_api_http_response()
        elif type(self.sensor_response) == subprocess.Popen:
            self.__parse_shell_response()

    def __parse_aws_api_http_response(self):
        self.json_parsed_response = json.loads(self.sensor_response)
        self.return_code = self.json_parsed_response['ResponseMetadata']['HTTPStatusCode']
        if self.return_code == '200':
            self.output = self.json_parsed_response
        else:
            self.error = self.json_parsed_response

    def __parse_shell_response(self):
        stdout, stderr = self.sensor_response.communicate(timeout=self.popen_communicate_timeout)
        self.return_code = self.sensor_response.returncode
        if self.return_code == 0:
            self.output = stdout
        else:
            self.error = stderr

    def __repr__(self):
        # ???
        # args = [i for i in (self.output, self.error) if i]
        return 'return code: {}, output: {}'.format(self.return_code, self.output)

    def __str__(self):
        return self.__repr__()


class Sensor:
    """ Sensor object factory

    """

    def __init__(self, name: str, shell: str=None, obj: classmethod=None):
        """ Sensor object

        :param name: Sensor's name
        :param shell: A string containing a shell command and its args
        :param obj: An class method that returns returncode, stdout and stderr
        """
        if shell and obj:
            raise SensorError

        self.name = name
        self.shell = shell
        self.obj = obj
        self.return_code = None
        self.stdout = None
        self.stderr = None
        self.response = {}

    def __runner(self):
        """ Executes the sensor. Sensor's can be objects or a cli command

        :return SensorResponse:
        """
        if self.obj:
            self.response = self.obj()
        elif self.shell:
            cmd = self.shell
            self.response = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        else:
            raise SensorError

        return SensorResponse(response=self.response)

    def __call__(self):
        return self.__runner()


class Sensors:

    def __init__(self, sensors: list=[]):
        """ Collection of sensors, adds only unique sensors

        :param sensors: List containing the sensor objects
        """
        self.sensors = sensors

    def __iter__(self):
        return iter(self.sensors)

    def add_sensor(self, **kwargs):
        name = kwargs.get('name')
        shell = kwargs.get('shell', None)
        obj = kwargs.get('obj', None)
        if shell and obj:
            raise 'The sensor cannot have two types.\n{}'.format(SensorError)
        elif shell:
            self.add_shell_sensor(name, shell)
        elif obj:
            self.add_obj_sensor(name, obj)

    def __delete__(self, sensor):
        if isinstance(sensor, self):
            self.sensors.remove(sensor)
        else:
            raise SensorError

    def __repr__(self):
        return self.sensors

    def add_shell_sensor(self, name, shell):
        if not Sensor(name=name, shell=shell) in self.sensors:
            self.sensors.append(Sensor(name=name, shell=shell))
        else:
            raise SensorError

    def add_obj_sensor(self, name, obj):
        if not Sensor(name=name, obj=obj) in self.sensors:
            self.sensors.append(Sensor(name=name, obj=obj))
        else:
            raise SensorError

    def run_all(self):
        responses = [s() for s in self.sensors]
        return responses


class AWSSensors:

    def __init__(self, tag: dict, sensor: str):
        """
        :self.values: it is a shared dictionary where the sensors stores the results of its inspections
        """
        self.values = {}
        self.ec2 = boto3.client('ec2', region_name='us-east-1')
        self.rds = boto3.client('rds', region_name='us-east-1')
        self.tag = tag
        self.sensor = sensor

    def __list_class_methods(self):
        return inspect.getmembers(self, predicate=inspect.ismethod)

    @staticmethod
    def __validate_aws_response(resource, response):

        if len(json.loads(response)[resource]) >= 1:
            return True
        else:
            return False

    def check_vpc_by_tag(self) -> SensorResponse:
        """ check if aws resource exists

        :param tag: {'project': 'project_name'}
        :return:
        """
        resource = 'Vpcs'
        key, value = self.tag.popitem()
        aws_response = self.ec2.describe_vpcs(Filters=[{'Name': 'tag:' + key, 'Values': [value]}])

        if self.__validate_aws_response(resource, aws_response):
            return_code, output, error = aws_response, None, 0
        else:
            return_code, output, error = 1, None, aws_response

        return SensorResponse(return_code, output, error)

    def run(self):
        try:
            obj = getattr(self, self.sensor)
            obj_response = obj()
            return obj_response
        except:
            raise SensorError


if __name__ == '__main__':
    # ACTIONS
    sensors = Sensors()
    # VPC/Network set
    sensors.add_shell_sensor(
        name='CreateVPC',
        shell='ls -ltr /tmp/'
    )
    sensors.add_shell_sensor(
        name='CreateDB',
        shell='ls -ltr'
    )
    response = sensors.run_all()
    print(response)
    for r in response:
        print(r)