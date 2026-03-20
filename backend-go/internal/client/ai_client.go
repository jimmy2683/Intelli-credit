package client

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"math"
	"net/http"
	"strings"
	"time"
)

// Default retry configuration
const (
	maxRetries    = 3
	baseDelay     = 1 * time.Second
	maxDelay      = 8 * time.Second
	retryableCeil = 500 // retry on 5xx errors
)

type AIClient struct {
	baseURL string
	http    *http.Client
	timeout time.Duration
}

func NewAIClient(baseURL string, timeout time.Duration) *AIClient {
	return &AIClient{
		baseURL: strings.TrimRight(baseURL, "/"),
		http: &http.Client{
			Timeout: timeout,
		},
		timeout: timeout,
	}
}

func (c *AIClient) Extract(payload any) (map[string]any, error) {
	return c.postWithRetry("/extract", payload)
}

func (c *AIClient) Research(payload any) (map[string]any, error) {
	return c.postWithRetry("/research", payload)
}

func (c *AIClient) Score(payload any) (map[string]any, error) {
	return c.postWithRetry("/score", payload)
}

func (c *AIClient) CAM(payload any) (map[string]any, error) {
	return c.postWithRetry("/cam", payload)
}

func (c *AIClient) Notes(payload any) (map[string]any, error) {
	return c.postWithRetry("/notes", payload)
}

func (c *AIClient) postWithRetry(path string, payload any) (map[string]any, error) {
	var lastErr error
	for attempt := 0; attempt <= maxRetries; attempt++ {
		if attempt > 0 {
			delay := time.Duration(math.Pow(2, float64(attempt-1))) * baseDelay
			if delay > maxDelay {
				delay = maxDelay
			}
			log.Printf("[ai_client] retry %d/%d for %s after %v", attempt, maxRetries, path, delay)
			time.Sleep(delay)
		}

		result, err := c.post(path, payload)
		if err == nil {
			return result, nil
		}
		lastErr = err

		// Only retry on connection/timeout errors, not on 4xx (client errors)
		if !isRetryable(err) {
			return nil, fmt.Errorf("non-retryable error on %s: %w", path, err)
		}
	}
	return nil, fmt.Errorf("all %d retries exhausted for %s: %w", maxRetries, path, lastErr)
}

func isRetryable(err error) bool {
	if err == nil {
		return false
	}
	errStr := err.Error()
	// Connection refused, timeout, and 5xx errors are retryable
	if strings.Contains(errStr, "connection refused") ||
		strings.Contains(errStr, "context deadline exceeded") ||
		strings.Contains(errStr, "timeout") ||
		strings.Contains(errStr, "status 5") {
		return true
	}
	return true // Default: retry on unknown errors
}

func (c *AIClient) post(path string, payload any) (map[string]any, error) {
	body, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("marshal payload: %w", err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), c.timeout)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+path, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.http.Do(req)
	if err != nil {
		return nil, fmt.Errorf("call ai service %s: %w", path, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		return nil, fmt.Errorf("ai service %s returned status %d", path, resp.StatusCode)
	}

	var out map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return nil, fmt.Errorf("decode ai response from %s: %w", path, err)
	}
	return out, nil
}
