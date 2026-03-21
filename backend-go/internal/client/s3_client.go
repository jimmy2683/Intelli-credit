package client

import (
	"context"
	"fmt"
	"io"
	"log"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/credentials"
	"github.com/aws/aws-sdk-go-v2/service/s3"
)

type S3Client struct {
	client *s3.Client
	bucket string
	region string
}

func NewS3Client(accessKey, secretKey, region, bucket string) (*S3Client, error) {
	if accessKey == "" || secretKey == "" || bucket == "" {
		return nil, fmt.Errorf("S3 credentials or bucket missing")
	}

	cfg, err := config.LoadDefaultConfig(context.TODO(),
		config.WithRegion(region),
		config.WithCredentialsProvider(credentials.NewStaticCredentialsProvider(accessKey, secretKey, "")),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to load SDK config: %w", err)
	}

	return &S3Client{
		client: s3.NewFromConfig(cfg),
		bucket: bucket,
		region: region,
	}, nil
}

func (s *S3Client) UploadFile(ctx context.Context, key string, body io.Reader, contentType string) (string, error) {
	_, err := s.client.PutObject(ctx, &s3.PutObjectInput{
		Bucket:      aws.String(s.bucket),
		Key:         aws.String(key),
		Body:        body,
		ContentType: aws.String(contentType),
	})
	if err != nil {
		return "", fmt.Errorf("S3 put object failed: %w", err)
	}

	// Construct s3 URI
	uri := fmt.Sprintf("s3://%s/%s", s.bucket, key)
	log.Printf("[s3] uploaded file to %s", uri)
	return uri, nil
}

func (s *S3Client) GetBucket() string {
	return s.bucket
}
