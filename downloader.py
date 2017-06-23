"""
PART 2: DOWNLOADER
Downloads the original images of queued wats onto S3.
"""
import helpers


def handler(event, context):
    """
    This handler is triggered by a DynamoDB stream. The event argument
    may contain several stream events that needs to be processed.
    """
    for url in helpers.get_queued_urls(event):  # Iterate the stream events.
        try:
            print 'Downloading', url
            s3_url = helpers.download_to_s3(url)  # Put the original on S3.
            print 'Done', s3_url
            helpers.register_status(url, 'downloaded')
        except Exception as e:
            # We handle errors and print them to the log, as Lambda would
            # retry the event otherwise.
            print 'Error', e
            helpers.register_status(url, 'error')
