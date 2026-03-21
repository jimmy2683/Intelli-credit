package config

import (
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/joho/godotenv"
)

type Config struct {
	BackendPort       string
	AIEngineBaseURL   string
	DataRoot          string
	DBPath            string
	CORSAllowedOrigin []string
	HTTPTimeout       time.Duration
	AWSAccessKey      string
	AWSSecretKey      string
	AWSRegion         string
	AWSS3Bucket       string
}

// Load environment variables (only once)
func init() {
	err := godotenv.Load()
	if err != nil {
		log.Println("⚠️ No .env file found (expected in production)")
	}
}

func Load() Config {
	timeoutSec := getEnvAsInt("BACKEND_HTTP_TIMEOUT_SEC", 180)
	dataRoot := getEnv("DATA_ROOT", "../data")

	cfg := Config{
		// Render-compatible port handling
		BackendPort:       getEnv("PORT", getEnv("BACKEND_PORT", "8080")),
		AIEngineBaseURL:   strings.TrimRight(getEnv("AI_ENGINE_BASE_URL", "http://localhost:8000"), "/"),
		DataRoot:          dataRoot,
		DBPath:            getEnv("DB_PATH", filepath.Join(dataRoot, "credit-intel.db")),
		CORSAllowedOrigin: getEnvAsList("CORS_ALLOWED_ORIGINS", "*"),
		HTTPTimeout:       time.Duration(timeoutSec) * time.Second,

		// AWS config (correct region default)
		AWSAccessKey: getEnv("AWS_ACCESS_KEY_ID", ""),
		AWSSecretKey: getEnv("AWS_SECRET_ACCESS_KEY", ""),
		AWSRegion:    getEnv("AWS_REGION", "ap-southeast-2"), // FIXED
		AWSS3Bucket:  getEnv("AWS_S3_BUCKET", ""),
	}

	// Validation (fail fast)
	if cfg.AWSAccessKey == "" || cfg.AWSSecretKey == "" {
		log.Println("⚠️ AWS credentials missing")
	}
	if cfg.AWSS3Bucket == "" {
		log.Println("⚠️ AWS_S3_BUCKET not set")
	}

	return cfg
}

func getEnv(key, fallback string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	return fallback
}

func getEnvAsInt(key string, fallback int) int {
	raw := os.Getenv(key)
	if raw == "" {
		return fallback
	}
	n, err := strconv.Atoi(raw)
	if err != nil {
		return fallback
	}
	return n
}

func getEnvAsList(key, fallback string) []string {
	raw := getEnv(key, fallback)
	parts := strings.Split(raw, ",")
	out := make([]string, 0, len(parts))

	for _, p := range parts {
		clean := strings.TrimSpace(p)
		if clean != "" {
			out = append(out, clean)
		}
	}

	if len(out) == 0 {
		return []string{"*"}
	}

	return out
}

// Optional: self ping (disabled on Render)
func StartSelfPing(port string) {
	// Skip in Render
	if os.Getenv("RENDER") != "" {
		log.Println("Skipping self-ping on Render")
		return
	}

	go func() {
		ticker := time.NewTicker(14 * time.Minute)
		defer ticker.Stop()

		for range ticker.C {
			url := "http://localhost:" + port + "/ping"

			resp, err := http.Get(url)
			if err != nil {
				log.Println("Self ping failed:", err)
				continue
			}

			resp.Body.Close()
			log.Println("Self ping successful:", url)
		}
	}()
}