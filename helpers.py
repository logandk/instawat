"""
HELPERS

This is where all the actual code is hidden away, in order to keep the
app and event handlers lean and tidy.
"""
import cStringIO
import datetime
import hashlib
import os
import sys
import time
import urllib2

# The boto3 library is always available on Lambda.
import boto3
from boto3.dynamodb.conditions import Key

# Since Pillow is bundled by serverless-wsgi, we need to load it from the
# .requirements directory.
root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(root, '.requirements'))
from PIL import Image, ImageOps  # noqa


dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])
s3 = boto3.resource('s3')
bucket = os.environ['BUCKET_NAME']


def get_wats():
    """
    Queries the DynamoDB GSI to get wats created today, in reverse order,
    limited to 30 items.
    """
    return table.query(
        IndexName='created_at-index',
        KeyConditionExpression=Key('created_at_date').eq(_today()),
        Limit=30,
        ScanIndexForward=False
    )['Items']


def create_wat(url):
    """
    Inserts the entry into DynamoDB. We need both the date and timestamp
    for the GSI to work.
    """
    table.put_item(Item={
        'url': url,
        'status': 'queued',
        'created_at_date': _today(),
        'created_at_time': int(time.time())
    })


def get_queued_urls(event):
    """
    Filters the DynamoDB stream event to get only queued wats.
    """
    for record in event['Records']:
        status = _deep_get(record, 'dynamodb', 'NewImage', 'status', 'S')
        if status == 'queued':
            yield _deep_get(record, 'dynamodb', 'Keys', 'url', 'S')


def get_s3_keys(event):
    """
    In practice, we only get a single record in the list.
    """
    for record in event['Records']:
        yield record['s3']['object']['key']


def download_to_s3(url):
    """
    Wraps the download and upload functions into one.
    """
    body = _download_url(url)
    key = _generate_filename(url)
    return _upload_original_to_s3(key, body, url)


def register_status(url, status):
    """
    Sets the status attribute of an existing wat. Used to indicate either
    download completion or errors.
    """
    table.update_item(
        Key={'url': url},
        UpdateExpression=(
            'SET #status = :status'),
        ExpressionAttributeValues={
            ':status': status
        },
        ExpressionAttributeNames={'#status': 'status'},
    )


def watify(key):
    """
    Download the original from S3, watify it and put a new image
    on S3 in a different folder.
    """
    body, original_url = _get_s3_object(key)
    watified = _overlay_image(body, 'watboy.png')
    watified_url = _upload_watified_to_s3(key, watified)
    return _update_completed_wat(original_url, watified_url)


def _update_completed_wat(url, watified_url):
    """
    Sets the wat status to completed and saves the URL of the watified version.
    """
    table.update_item(
        Key={'url': url},
        UpdateExpression=(
            'SET watified_url = :watified_url, #status = :status'),
        ExpressionAttributeValues={
            ':watified_url': watified_url,
            ':status': 'completed'
        },
        ExpressionAttributeNames={'#status': 'status'},
    )
    return watified_url


def _today():
    """
    Today's date in ISO format, e.g. 2017-06-23
    """
    return datetime.date.today().isoformat()


def _get_s3_object(key):
    """
    Reads the object given by key from S3 and returns the binary contents,
    including the `original url` from metadata.
    """
    s3_object = s3.Object(bucket, key).get()
    body = s3_object['Body'].read()
    original_url = s3_object['Metadata']['original_url']
    return (body, original_url)


def _upload_original_to_s3(key, body, original_url):
    """
    upload the original binary contents to s3, set its `original_url` in
    metadata and return its public url.
    """
    s3.Object(bucket, 'original/{}'.format(key)).put(
        ACL='public-read',
        ContentType='image/jpeg',
        Body=body,
        Metadata={'original_url': original_url})
    return 'https://s3.amazonaws.com/{}/original/{}'.format(bucket, key)


def _upload_watified_to_s3(key, body):
    """
    upload the watified binary contents to s3 and return its public url.
    """
    key = os.path.basename(key)
    s3.Object(bucket, 'watified/{}'.format(key)).put(
        ACL='public-read',
        ContentType='image/jpeg',
        Body=body)
    return 'https://s3.amazonaws.com/{}/watified/{}'.format(bucket, key)


def _download_url(url):
    """
    Download a file from the URL, timeout in 5 secs.
    """
    return urllib2.urlopen(url, None, 5).read()


def _generate_filename(url):
    """
    Hash the original URL to get a safe filename.
    """
    sha1 = hashlib.sha1()
    sha1.update(url)
    return '{}.jpg'.format(sha1.hexdigest())


def _overlay_image(original_bytes, overlay_file):
    """
    This is where the secret sauce is made, take the one image and put
    it on top of the other one! It's easy!
    """
    original = _image_from_bytes(original_bytes)
    overlay = _scale_image_to_match(Image.open(overlay_file), original)

    result = original.copy().convert('RGBA')
    result.paste(overlay, (0, 0), mask=overlay)

    return _image_to_bytes(result)


def _scale_image_to_match(image, reference):
    """
    Scales image to match the size of the reference image, upscaling if
    necessary.
    """
    if image.size[0] > reference.size[0] or image.size[1] > reference.size[1]:
        image.thumbnail(reference.size)
    else:
        image = ImageOps.fit(image, reference.size)
    return image


def _image_from_bytes(image_bytes):
    """
    Converts a string to a PIL Image object.
    """
    return Image.open(cStringIO.StringIO(image_bytes))


def _image_to_bytes(image):
    """
    Converts a PIL Image object to a string.
    """
    output = cStringIO.StringIO()
    image.save(output, 'JPEG')
    jpeg_data = output.getvalue()
    output.close()
    return jpeg_data


def _deep_get(dictionary, *keys):
    """
    Get a deeply nested value from a dictionary, returning None if any key
    in the chain is not found.
    """
    return reduce(lambda d, key: d.get(key) if d else None, keys, dictionary)
