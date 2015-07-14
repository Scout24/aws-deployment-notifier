import dnot
from mock import patch
import unittest2


class NotifierTest(unittest2.TestCase):
    @patch("dnot.boto.sns.connect_to_region")
    def test_parameters_are_submitted(self, connect_to_region_mock):
        topic = "abc"
        region = "eu-west-2"
        notifier = dnot.Notifier(sns_region=region)

        notifier.publish(sns_topic_arn=topic, stack_name="stack1", params='{ "key": "value" }')

        connect_to_region_mock.assert_called_with(region)
        connect_to_region_mock.return_value.publish.assert_called_with(
            topic=topic,
            message='{"stackName": "stack1", "region": "eu-west-1", "params": {"key": "value"}}')
