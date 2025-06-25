import time


def handler(event, context):

    # Get the job name from the event
    job_name = event.get("jobName")
    print(f"Record processor got job name: {job_name}")

    time.sleep(10)

    # Pass job name forward to next state
    return {"statusCode": 200, "jobName": job_name}
