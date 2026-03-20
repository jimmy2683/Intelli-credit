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
	aiClient := client.NewAIClient(cfg.AIEngineBaseURL, cfg.HTTPTimeout)
	caseService := service.NewCaseService(cfg, aiClient, db)
	caseController := controller.NewCaseController(caseService)

	handler := router.New(cfg, caseController)
	server := &http.Server{
		Addr:         ":" + cfg.BackendPort,
		Handler:      handler,
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 60 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	go func() {
		log.Printf("backend-go listening on :%s", cfg.BackendPort)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("server failed: %v", err)
		}
	}()

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
