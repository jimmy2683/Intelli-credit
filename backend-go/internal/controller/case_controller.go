package controller

import (
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"

	"credit-intel/backend-go/internal/model"
	"credit-intel/backend-go/internal/service"
	"credit-intel/backend-go/internal/utils"
)

type CaseController struct {
	caseService *service.CaseService
}

func NewCaseController(caseService *service.CaseService) *CaseController {
	return &CaseController{caseService: caseService}
}

func (c *CaseController) Health(w http.ResponseWriter, _ *http.Request) {
	utils.WriteJSON(w, http.StatusOK, map[string]any{
		"status":  "ok",
		"service": "backend-go",
	})
}

func (c *CaseController) CreateCase(w http.ResponseWriter, r *http.Request) {
	var req model.CreateCaseRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		utils.WriteError(w, http.StatusBadRequest, "invalid JSON body")
		return
	}
	if strings.TrimSpace(req.CompanyName) == "" {
		utils.WriteError(w, http.StatusBadRequest, "company_name is required")
		return
	}

	out := c.caseService.CreateCase(req)
	utils.WriteJSON(w, http.StatusCreated, out)
}

func (c *CaseController) HandleCaseRoutes(w http.ResponseWriter, r *http.Request) {
	id, action, subAction, ok := parseCasePath(r.URL.Path)
	if !ok {
		utils.WriteError(w, http.StatusNotFound, "route not found")
		return
	}

	switch {
	case r.Method == http.MethodGet && action == "":
		c.getCase(w, id)
	case r.Method == http.MethodPost && action == "upload":
		c.uploadFiles(w, r, id)
	case r.Method == http.MethodPost && action == "notes":
		c.updateNotes(w, r, id)
	case r.Method == http.MethodPost && action == "analyze":
		c.analyzeCase(w, id)
	case r.Method == http.MethodGet && action == "cam" && subAction == "":
		c.getCAM(w, id)
	case r.Method == http.MethodGet && action == "cam" && subAction == "download":
		c.downloadCAM(w, r, id)
	default:
		utils.WriteError(w, http.StatusMethodNotAllowed, "method not allowed")
	}
}

func (c *CaseController) getCase(w http.ResponseWriter, id string) {
	cc, err := c.caseService.GetCase(id)
	if err != nil {
		if errors.Is(err, service.ErrCaseNotFound) {
			utils.WriteError(w, http.StatusNotFound, err.Error())
			return
		}
		utils.WriteError(w, http.StatusInternalServerError, "failed to fetch case")
		return
	}
	utils.WriteJSON(w, http.StatusOK, cc)
}

func (c *CaseController) uploadFiles(w http.ResponseWriter, r *http.Request, id string) {
	if err := r.ParseMultipartForm(32 << 20); err != nil {
		utils.WriteError(w, http.StatusBadRequest, "invalid multipart form")
		return
	}

	files := r.MultipartForm.File["files"]
	if len(files) == 0 {
		utils.WriteError(w, http.StatusBadRequest, "files field is required")
		return
	}

	saved, err := c.caseService.SaveUploadedFiles(id, files)
	if err != nil {
		if errors.Is(err, service.ErrCaseNotFound) {
			utils.WriteError(w, http.StatusNotFound, err.Error())
			return
		}
		log.Printf("upload error: %v", err)
		utils.WriteError(w, http.StatusInternalServerError, "failed to store files")
		return
	}

	utils.WriteJSON(w, http.StatusOK, map[string]any{
		"message": "files uploaded",
		"files":   saved,
	})
}

func (c *CaseController) analyzeCase(w http.ResponseWriter, id string) {
	out, err := c.caseService.AnalyzeCase(id)
	if err != nil {
		if errors.Is(err, service.ErrCaseNotFound) {
			utils.WriteError(w, http.StatusNotFound, err.Error())
			return
		}
		log.Printf("analyze error: %v", err)
		utils.WriteError(w, http.StatusInternalServerError, "failed to analyze case")
		return
	}
	utils.WriteJSON(w, http.StatusAccepted, out)
}

func (c *CaseController) getCAM(w http.ResponseWriter, id string) {
	out, err := c.caseService.GetCAM(id)
	if err != nil {
		if errors.Is(err, service.ErrCaseNotFound) {
			utils.WriteError(w, http.StatusNotFound, err.Error())
			return
		}
		utils.WriteError(w, http.StatusInternalServerError, "failed to fetch cam")
		return
	}
	utils.WriteJSON(w, http.StatusOK, out)
}

func (c *CaseController) downloadCAM(w http.ResponseWriter, r *http.Request, id string) {
	filePath, contentType, fileName, err := c.caseService.GetCAMFileInfo(id)
	if err != nil {
		if errors.Is(err, service.ErrCaseNotFound) {
			utils.WriteError(w, http.StatusNotFound, err.Error())
			return
		}
		utils.WriteError(w, http.StatusNotFound, fmt.Sprintf("CAM document not available: %v", err))
		return
	}

	file, err := os.Open(filePath)
	if err != nil {
		utils.WriteError(w, http.StatusInternalServerError, "failed to open CAM file")
		return
	}
	defer file.Close()

	info, _ := file.Stat()
	w.Header().Set("Content-Type", contentType)
	w.Header().Set("Content-Disposition", fmt.Sprintf("attachment; filename=\"%s\"", fileName))
	http.ServeContent(w, r, info.Name(), info.ModTime(), file)
}

func (c *CaseController) updateNotes(w http.ResponseWriter, r *http.Request, id string) {
	var req model.UpdateNotesRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		utils.WriteError(w, http.StatusBadRequest, "invalid JSON body")
		return
	}
	out, err := c.caseService.UpdateOfficerNotes(id, req.OfficerNotes)
	if err != nil {
		if errors.Is(err, service.ErrCaseNotFound) {
			utils.WriteError(w, http.StatusNotFound, err.Error())
			return
		}
		utils.WriteError(w, http.StatusInternalServerError, "failed to update notes")
		return
	}
	utils.WriteJSON(w, http.StatusOK, out)
}

func parseCasePath(path string) (id, action, subAction string, ok bool) {
	trimmed := strings.Trim(path, "/")
	parts := strings.Split(trimmed, "/")
	if len(parts) < 2 || parts[0] != "cases" {
		return "", "", "", false
	}
	id = parts[1]
	if id == "" {
		return "", "", "", false
	}
	if len(parts) == 2 {
		return id, "", "", true
	}
	if len(parts) == 3 {
		return id, parts[2], "", true
	}
	if len(parts) == 4 {
		return id, parts[2], parts[3], true
	}
	return "", "", "", false
}
