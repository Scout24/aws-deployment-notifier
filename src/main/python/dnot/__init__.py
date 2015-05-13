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

import boto
import logging
import json
from boto import sqs, sns

VALID_RESOURCE_STATES = ['UPDATE_COMPLETE', 'CREATION_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE', 'ROLLBACK_COMPLETE']


class Notifier(object):
    def __init__(self, region='eu-west-1', sns_topic_arn=None, stack_name=None, ami_id=None):
        self.logger = logging.getLogger(__name__)
        self.region = region
        self.sns_topic_arn = sns_topic_arn
        self.stack_name = stack_name
        self.ami_id = ami_id
        self.sns_connection = boto.sns.connect_to_region('eu-west-1')

    def publish(self):
        self.sns_connection.publish(topic=self.sns_topic_arn, message=json.dumps(
            {'AmiId': self.ami_id, 'StackName': self.stack_name}))


class Receiver(object):
    def __init__(self, region='eu-west-1', sqs_queue_arn=None, stack_name=None):
        self.logger = logging.getLogger(__name__)
        self.stack_name = stack_name
        self.sqs_connection = boto.sqs.connect_to_region(region)
        self.sqs_queue = self.sqs_connection.get_queue(sqs_queue_arn)

    def delete_message(self, message):
        self.logger.info('Deleting Message')
        self.sqs_connection.delete_message(self.sqs_queue, message)

    def process_message(self, message):
        json_data = json.loads(message.get_body())
        message_data = json_data['Message'].rstrip()
        pairs = message_data.splitlines()
        return dict(pair.split('=') for pair in pairs)

    def poll(self):
        received_corresponding_message = False
        
        while not received_corresponding_message:
            try:
                messages = self.sqs_queue.get_messages()
                for message in messages:
                    message_data = self.process_message(message)
                    stack_name = message_data['StackName'].strip('\'')
                    resource_status = message_data['ResourceStatus'].strip('\'')
                    if stack_name is self.stack_name and resource_status in VALID_RESOURCE_STATES:
                        self.logger.info('CloudFormation stack is in state {0}'.format(resource_status))
                        message.delete()
                        received_corresponding_message = True
            except Exception, e:
                self.logger.exception(e)