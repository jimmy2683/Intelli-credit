package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"credit-intel/backend-go/internal/client"
	"credit-intel/backend-go/internal/config"
	"credit-intel/backend-go/internal/controller"
	"credit-intel/backend-go/internal/router"
	"credit-intel/backend-go/internal/service"
	"credit-intel/backend-go/internal/store"
)

func main() {
	log.Println("🔥 MAIN STARTED")

	cfg := config.Load()

	// ── Database ──
	db, err := store.Open(cfg.DBPath)
	if err != nil {
		log.Fatalf("failed to open database at %s: %v", cfg.DBPath, err)
	}
	defer db.Close()
	log.Printf("database opened at %s", cfg.DBPath)

	db.SeedSampleData()

	// ── Services ──
	var s3Client *client.S3Client
	if cfg.AWSAccessKey != "" && cfg.AWSSecretKey != "" && cfg.AWSS3Bucket != "" {
		var err error
		s3Client, err = client.NewS3Client(cfg.AWSAccessKey, cfg.AWSSecretKey, cfg.AWSRegion, cfg.AWSS3Bucket)
		if err != nil {
			log.Printf("failed to initialize s3 client: %v", err)
		} else {
			log.Printf("S3 client initialized for bucket: %s", cfg.AWSS3Bucket)
		}
	} else {
		log.Println("S3 credentials not provided, falling back to local storage")
	}

	// log.Println("AI BASE URL:", cfg.AIEngineBaseURL)
	aiClient := client.NewAIClient(cfg.AIEngineBaseURL, cfg.HTTPTimeout)
	caseService := service.NewCaseService(cfg, aiClient, s3Client, db)
	caseController := controller.NewCaseController(caseService)

	handler := router.New(cfg, caseController)

	server := &http.Server{
		Addr:         ":" + cfg.BackendPort,
		Handler:      handler,
		ReadTimeout:  300 * time.Second,
		WriteTimeout: 300 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	// FIX: start server in main thread (NOT goroutine)
	go func() {
		log.Printf("backend-go listening on :%s", cfg.BackendPort)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("server failed: %v", err)
		}
	}()

	// Ensure server actually starts before waiting
	time.Sleep(2 * time.Second)

	// ── Graceful shutdown ──
	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)

	<-stop
	log.Println("shutdown signal received")

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	if err := server.Shutdown(ctx); err != nil {
		log.Printf("graceful shutdown error: %v", err)
	}

	log.Println("server stopped")
}