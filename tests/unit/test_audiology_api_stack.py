import aws_cdk as core
import aws_cdk.assertions as assertions

from audiology_api.audiology_api_stack import AudiologyApiStack

# example tests. To run these tests, uncomment this file along with the example
# resource in audiology_api/audiology_api_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = AudiologyApiStack(app, "audiology-api")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
