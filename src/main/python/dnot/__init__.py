# AWS Deployment Notifier - Automate your Stack Updates!
# Copyright 2015 Immobilien Scout GmbH
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import time
import logging
import json
import datetime

from boto import sns, sqs
import pytz

VALID_RESOURCE_STATES = ['UPDATE_COMPLETE', 'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS']


class Notifier(object):
    def __init__(self, sns_region='eu-west-1'):
        self.logger = logging.getLogger(__name__)
        self.sns_connection = sns.connect_to_region(sns_region)

    def publish(self, sns_topic_arn, stack_name, params, result_topic, region="eu-west-1"):
        self.sns_connection.publish(topic=sns_topic_arn, message=json.dumps(
            {'stackName': stack_name, 'region': region, 'notificationARN': result_topic, 'params': json.loads(params)})
        )
        self.logger.info("Published stack update notification for: {0} with params: {1}"
                         .format(stack_name, params))


class Receiver(object):
    def __init__(self, queue_name, queue_account, stack_name, region='eu-west-1',):
        self.logger = logging.getLogger(__name__)
        self.stack_name = stack_name
        self.sqs_connection = sqs.connect_to_region(region)
        self.sqs_queue = self.sqs_connection.get_queue(queue_name=queue_name, owner_acct_id=queue_account)
        if not self.sqs_queue:
            raise Exception("Unable to find SQS queue for name: {0} in account: {1}"
                            .format(queue_name, queue_account))

    def get_cloudformation_message_data(self, body):
        message_data = body['Message'].rstrip()
        lines = message_data.splitlines()
        return self.strip_quotes_from_values(dict(line.split("='") for line in lines if "='" in line))

    def get_body(self, message):
        data = json.loads(message.get_body())
        return self.strip_quotes_from_values(data)

    def strip_quotes_from_values(self, dictionary):
        result = {}
        for key, value in dictionary.items():
            result[key] = value.strip("'")
        return result

    def wait_for_deployment_result(self, start_time=None):
        start_time = start_time or pytz.UTC.localize(datetime.datetime.utcnow())

        while True:
            if self.is_done(start_time):
                break

            time.sleep(1)

    def is_done(self, start_time):
        messages = self.sqs_queue.get_messages()
        self.logger.info("Got messages: {0}".format(len(messages)))

        for message in messages:
            self.logger.debug("Processing message {0}".format(vars(message)))
            body = self.get_body(message)

            message_timestamp = datetime.datetime(
                *time.strptime(body['Timestamp'], "%Y-%m-%dT%H:%M:%S.%fZ")[0:6], tzinfo=pytz.utc)
            message_data = self.get_cloudformation_message_data(body)
            resource_status = message_data['ResourceStatus']
            stack_name = message_data['StackName']
            resource_type = message_data['ResourceType']

            if stack_name == self.stack_name:
                message.delete()

                if message_timestamp < start_time:
                    self.logger.debug("Discarding stale event: {0}".format(body))
                else:
                    self.logger.info(
                        "At (UTC): {0} stack name: {1}, resource status: {2} for resource type: {3}"
                            .format(message_timestamp, stack_name, resource_status, resource_type))

                    if resource_status in VALID_RESOURCE_STATES and resource_type == "AWS::CloudFormation::Stack":
                        self.logger.info("Update of stack: {0} succeeded at (UTC) {1}: {2}"
                                         .format(stack_name, message_timestamp,
                                                 message_data['ResourceStatusReason']))
                        return True
                    elif resource_status.startswith("UPDATE_ROLLBACK"):
                        raise Exception("Update failed: {0}".format(message_data['ResourceStatusReason']))
