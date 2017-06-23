"""
PART 3: THE WATIFIER
Patent pending.
"""
import helpers


def handler(event, context):
    """
    This handler is triggered by an S3 notification. The event argument
    will contain a list of S3 keys, that currently always holds a single
    item. We iterate the list anyway, to account for any future changes
    from Amazon's side.
    """
    for key in helpers.get_s3_keys(event):  # Iterate S3 event records.
        try:
            print 'Watifying', key
            url = helpers.watify(key)  # Do the magic!
            print 'Done', url
        except Exception as e:
            # Any errors printed here will be visible in the CloudWatch log.
            print 'Error', e
            helpers.register_status(url, 'error')
