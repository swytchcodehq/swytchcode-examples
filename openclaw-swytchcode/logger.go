// Package main provides CSV logging for the GitHub triage bot.
package main

import (
	"encoding/csv"
	"fmt"
	"os"
	"time"
)

const logFile = "issues_log.csv"

// LogEntry represents a single row in the CSV log.
type LogEntry struct {
	IssueURL    string
	IssueTitle  string
	IssueType   IssueType
	CommentBody string
	CommentedAt time.Time
}

// LogComment appends a log entry to issues_log.csv.
// Creates the file with headers if it does not exist.
func LogComment(entry LogEntry) error {
	fileExists := true
	if _, err := os.Stat(logFile); os.IsNotExist(err) {
		fileExists = false
	}

	f, err := os.OpenFile(logFile, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return fmt.Errorf("open log file: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	if !fileExists {
		if err := w.Write([]string{"issue_url", "issue_title", "issue_type", "comment_body", "commented_at"}); err != nil {
			return fmt.Errorf("write csv header: %w", err)
		}
	}

	if err := w.Write([]string{
		entry.IssueURL,
		entry.IssueTitle,
		string(entry.IssueType),
		entry.CommentBody,
		entry.CommentedAt.Format(time.RFC3339),
	}); err != nil {
		return fmt.Errorf("write csv row: %w", err)
	}

	return nil
}
