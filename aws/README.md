![image](/images/cs-logo.png)
# aws-hide-host

## Introduction

Event driven solution to automatically remove AWS Instances from CrowdStrike upon termination.

## Architectural Overview

The solution infrastructure is deployed via AWS CloudFormation templates. The template will automatically launch AWS CloudFormation StackSets in each of the desired regions.

The following architectural diagram illustrates the resources deployed in an AWS account.

![image](/images/diagram.png)

### Workflow
1. An AWS EC2 Instance is terminated.
2. The EC2 Instance State-change notification triggers an EventBridge Rule in the same Region.
3. The EventBridge rule targets a custom Event Bus.
4. The custom Event Bus applies to another EventBridge Rule which targets Lambda.
5. The Lambda function receives and processes the event.
6. The Lambda function retrieves Falcon API Keys from either Secrets Manager or Parameter Store.
7. The Lambda function calls the Falcon API to hide the terminated instance-id from the Falcon console.

## Prerequisites

Create Falcon API Keys with the following scope: Hosts Read & Write

## CloudFormation Parameters

**CrowdStrike Falcon API Keys**
| Parameter|Description|
|---|---|
|Your CrowdStrike Falcon CLoud| u-1, us-2 or eu-1|
|Create Secret for API Keys| whether to provide Falcon API Keys and store as a secret|
|Your Falcon API Client ID| only provide if Create Secret for API Keys = true|
|Your Falcon API Secret| only provide if Create Secret for API Keys = true|
|Name of SSM Parameter to store Falcon API Client ID| if you do not want to store API Keys as a secret, the SSM Paramter name where the API Client ID is stored|
|Name of SSM Parameter to store Falcon API Client Secret| if you do not want to store API Keys as a secret, the SSM Paramter name where the API Secret is stored|

**Activate Regions**
| Parameter|Description|
|---|---|
|Activate regions to deploy EventBridge rules| list of regions to enroll with CrowdStrike Hide Host|

**Define Resource Names** 
These parameters have predefined values, but may be modified if your Organization requires.
| Parameter|
|---|
|Name of Secret to store Falcon API Keys|
|Lambda Function Name|
|Event Bus Name|
|EventBridge Rule Name|
|EventBridge Role Name|
|EventBridge Rule StackSet Name|
|StackSet Admin Role Name|
|StackSet Execution Role Name|


## Contribution Notes

> **Note** <br>
> For ease of deployment via CloudFormation and not introducing any custom resources or manual steps to seed the package in an S3 bucket, the code is embedded in the CloudFormation template and is zip'ed automatically by CloudFormation. This is mentioned to remind any contributors to update both references of the Lambda code where applicable.