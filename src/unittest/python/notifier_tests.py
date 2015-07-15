import dnot
from mock import patch
import unittest2


class NotifierTest(unittest2.TestCase):
    @patch("dnot.boto.sns.connect_to_region")
    def test_parameters_are_submitted(self, connect_to_region_mock):
        topic = "abc"
        region = "eu-west-2"
        result_topic = "result"
        stack_name = "stack1"
        params = '{"key": "value"}'

        notifier = dnot.Notifier(sns_region=region)
        notifier.publish(sns_topic_arn=topic, stack_name=stack_name, result_topic=result_topic, params=params)

        connect_to_region_mock.assert_called_with(region)
        connect_to_region_mock.return_value.publish.assert_called_with(
            topic=topic,
            message='{{"stackName": "{0}", "notificationARN": "{1}", "region": "eu-west-1", "params": {2}}}'.format(
                stack_name,
                result_topic,
                params))
