package config

import (
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

type Config struct {
	BackendPort       string
	AIEngineBaseURL   string
	DataRoot          string
	DBPath            string
	CORSAllowedOrigin []string
	HTTPTimeout       time.Duration
}

func Load() Config {
	timeoutSec := getEnvAsInt("BACKEND_HTTP_TIMEOUT_SEC", 15)
	dataRoot := getEnv("DATA_ROOT", "./data")
	return Config{
		BackendPort:       getEnv("BACKEND_PORT", "8080"),
		AIEngineBaseURL:   strings.TrimRight(getEnv("AI_ENGINE_BASE_URL", "http://localhost:8000"), "/"),
		DataRoot:          dataRoot,
		DBPath:            getEnv("DB_PATH", filepath.Join(dataRoot, "credit-intel.db")),
		CORSAllowedOrigin: getEnvAsList("CORS_ALLOWED_ORIGINS", "*"),
		HTTPTimeout:       time.Duration(timeoutSec) * time.Second,
	}
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
