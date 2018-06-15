
# coding: utf-8

# In[1]:


import os
import requests
import json
import urllib

#AWS python lib: Install via pip.
import boto3


msft_api_key = 'TODO: YOUR KEY FOR MSFT CONGNITIVE SERVICES'
google_api_key = 'TODO: YOUR KEY FOR Google cloud SERVICES'

#TODO: You must have configured AWS CLI for this to work. Simple to install and configure.
session = boto3.Session()
# Any clients created from this session will use credentials
# from the [dev] section of ~/.aws/credentials.

s3 = session.resource('s3', region_name='us-east-1')
s3Client = session.client('s3', region_name='us-east-1')
awsRekoclient = session.client('rekognition', region_name='us-east-1');

namespacePrefix="com.test."
#s3 bucket name where we will upload all the images.
ocrBucketName = namespacePrefix + 'ocr';

#where you have unzipped the dataset. TODO:
datasetFilePath = 'TODO: Path to where you have stored the downloaded dataset'



def getPostJson (url, params, data, headers) :
    try:
        response = requests.post(url, params=params, json=data, headers=headers)
        #print response
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        print "exception in put " + str(response.json())
        print(err)
        raise
    data = None
    if response:
        try:
            data = response.json();
        except Exception as e:
            print(e)
            data = None
    return data;

def s3MayBeCreateBucket(s3Resource, bucketName) :
    if not (s3Resource.Bucket(bucketName) in s3Resource.buckets.all()):
        print ("creating bucket")
        return s3Resource.create_bucket(Bucket=bucketName)
    else :
        return s3Resource.Bucket(bucketName);
        
def uploadImage(s3Resource, bucket, filePath, key):
    print "uploading file " + filePath + " for key = " + key
    bucket.upload_file(filePath, key, ExtraArgs={'ACL':'public-read'})

def getTextFromMsft(s3Bucket, s3Key):
    try:
        msft_face_api_headers = { 'Content-Type': 'application/json', 'Ocp-Apim-Subscription-Key': msft_api_key}
        url="https://westcentralus.api.cognitive.microsoft.com/vision/v1.0/ocr?language=unk&detectOrientation =true"
        image_url = "https://s3.amazonaws.com/" + s3Bucket + "/" + s3Key;
        print "trying image " + image_url;
        data={"url": image_url}
        linesStr=[]
        response = getPostJson(url, None, data, msft_face_api_headers);
        #print response
        for region in response["regions"]:
            for line in region["lines"]:
                lineStr =""
                for word in line["words"]:
                    lineStr += word["text"] + " "
                linesStr.append(lineStr)
        return linesStr;
    except Exception as e:
        print(e)
    return [];

def getTextFromGoogle(s3Bucket, s3Key):
    try:
        url="https://vision.googleapis.com/v1/images:annotate?key=" + google_api_key;
        image_url = "https://s3.amazonaws.com/" + s3Bucket + "/" + s3Key;
        print "trying image " + image_url;
        data={"requests": [
                {"image":
                 {"source": 
                  {"imageUri":  image_url}
                },
                 "features": [{
                    "type": "TEXT_DETECTION"
                 }]
                }]
            };

        response = getPostJson(url, None, data, None);
        #print json.dumps(response)
        text="";
        if "textAnnotations" in response["responses"][0]:
            text=response["responses"][0]["textAnnotations"][0]["description"]
        return text.split('\n');
    except Exception as e:
        print(e)
    return [];


def getTextFromAws(s3Bucket, s3Key):
    try:
        response = awsRekoclient.detect_text(Image={
                'S3Object': {
                    'Bucket': s3Bucket,
                    'Name': s3Key,
                }
            }
        );
        #print response
        text=""
        if len(response["TextDetections"]) > 0:
            text=response["TextDetections"][0]["DetectedText"];
        return text.split('\n');
    except Exception as e:
        print(e)
    return [];

    


# In[2]:


#read the image filenames and the text present in the image 
imageTextMapping=dict();
with open(datasetFilePath + 'annotations.txt', 'r') as f:
    for line in f:
        fileName = line.split('\n')[0]
        text = line.split('\n')[1]
        imageTextMapping[fileName] = text


# In[5]:


#upload all images to S3, since AWS only works with S3 uploaded images.
bucketName = ocrBucketName
bucket=s3MayBeCreateBucket(s3, bucketName)
totalNumSamples=500
count=0;
testItems=[];
for fileName in imageTextMapping:
    count +=1
    testItems.append(fileName)
    text=imageTextMapping[fileName]
    print "filepath = " + datasetFilePath + fileName + " text = " + text
    uploadImage(s3, bucket, datasetFilePath + fileName, fileName)
    if count > totalNumSamples:
        break


# In[ ]:


#validate the results
import time
stats=[]
for fileName in testItems:
    text=imageTextMapping[fileName];
    print "Testing for file " + fileName + " Expected text = " + text;
    msftText=getTextFromMsft(bucketName, fileName);
    gglText=getTextFromGoogle(bucketName, fileName);
    awsText=getTextFromAws(bucketName, fileName);
    stats.append((item, text, msftText, gglText, awsText));
    print "Response " + str(msftText) + " ," + str(gglText) + ", " + str(awsText)
    time.sleep(3)


# In[ ]:


#results.
# we make sure that the returned strings from each of these APIs is cleaned. We make all text comparision 
# in case-insensitive manner (by lower casing) and remove all special characters from the returned strings like '.' ',' etc
import re

msft_c = [x for x in stats  if len(x[2]) > 0 and x[1].lower().strip() in map(lambda x:re.sub('[^A-Za-z0-9 ]+', '', x.lower().strip()),x[2])]
msft_w = [x for x in stats  if len(x[2]) > 0 and x[2][0] and x[1].lower().strip() not in map(lambda x:re.sub('[^A-Za-z0-9 ]+', '',x.lower().strip()),x[2])]
msft_n = [x for x in stats  if len(x[2]) == 0 or not x[2][0]]
print "MSFT correct# = " + str(len(msft_c))
print "MSFT wrong# = " + str(len(msft_w))
print "MSFT No Result# = " + str(len(msft_n))
print ""

ggl_c = [x for x in stats  if len(x[3]) > 0 and x[1].lower().strip() in map(lambda x:re.sub('[^A-Za-z0-9 ]+', '',x.lower().strip()),x[3])]
ggl_w = [x for x in stats  if len(x[3]) > 0 and x[3][0] and x[1].lower().strip() not in map(lambda x:re.sub('[^A-Za-z0-9 ]+', '',x.lower().strip()),x[3])]
ggl_n = [x for x in stats  if len(x[3]) == 0 or not x[3][0]]
print "GGL correct# = " + str(len(ggl_c))
print "GGL wrong# = " + str(len(ggl_w))
print "GGL No Result# = " + str(len(ggl_n))
print ""

aws_c = [x for x in stats  if len(x[4]) > 0 and x[1].lower().strip() in map(lambda x:re.sub('[^A-Za-z0-9 ]+', '',x.lower().strip()),x[4])]
aws_w = [x for x in stats  if len(x[4]) > 0 and x[4][0]  and x[1].lower().strip() not in map(lambda x:re.sub('[^A-Za-z0-9 ]+', '',x.lower().strip()),x[4])]
aws_n = [x for x in stats  if len(x[4]) == 0 or not x[4][0]]
print "AWS correct# = " + str(len(aws_c))
print "AWS wrong# = " + str(len(aws_w))
print "AWS No Result# = " + str(len(aws_n))
print ""

#over all stats for text detection
all_c = [x for x in msft_c if x in ggl_c and x in aws_c]
all_w = [x for x in msft_w if x in ggl_w and x in aws_w]
all_n = [x for x in msft_n if x in ggl_n and x in aws_n]
any_c = [x for x in stats if x in msft_c or x in ggl_c or x in aws_c and x not in msft_w and x not in ggl_w and x not in aws_w]


print "All correct# = " + str(len(all_c))
print "All wrong# = " + str(len(all_w))
print "All No Result# = " + str(len(all_n))
print "Any correct# = " + str(len(any_c))

