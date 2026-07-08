// Package main is the GitHub Issue Triage Bot.
// It fetches open issues from a GitHub repo, classifies them using keyword
// matching (with swytchcode MCP as the AI layer), posts a relevant comment
// template, and logs everything to issues_log.csv.
//
// Usage:
//
//	GITHUB_TOKEN=<pat> GITHUB_OWNER=<owner> GITHUB_REPO=<repo> go run .
package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"time"
)

func main() {
	// Read config from environment variables
	token := mustEnv("GITHUB_TOKEN")
	owner := mustEnv("GITHUB_OWNER")
	repo := mustEnv("GITHUB_REPO")

	// Max comments per run — agreed rule: 5-10/day max
	maxComments := 5

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	log.Printf("Starting triage bot for %s/%s", owner, repo)

	// Step 1: Fetch open issues
	issues, err := FetchIssues(ctx, token, owner, repo)
	if err != nil {
		log.Fatalf("fetch issues: %v", err)
	}
	log.Printf("Found %d open issues", len(issues))

	commenter := NewGitHubCommenter(token)
	commented := 0

	for _, issue := range issues {
		if commented >= maxComments {
			log.Printf("Reached max comments limit (%d), stopping", maxComments)
			break
		}

		log.Printf("Processing issue #%d: %s", issue.Number, issue.Title)

		// Step 2: Classify the issue
		issueType, err := classifyIssue(ctx, issue.Title, issue.Body)
		if err != nil {
			log.Printf("classify issue #%d: %v — skipping", issue.Number, err)
			continue
		}
		log.Printf("Issue #%d classified as: %s", issue.Number, issueType)

		// Skip unknown issues
		if issueType == IssueTypeUnknown {
			log.Printf("Issue #%d is unknown type — skipping", issue.Number)
			continue
		}

		// Step 3: Get the comment template
		comment := Template(issueType)
		if comment == "" {
			log.Printf("No template for issue type %s — skipping", issueType)
			continue
		}

		// Step 4: Post the comment
		if err := commenter.PostComment(ctx, owner, repo, issue.Number, comment); err != nil {
			log.Printf("post comment on issue #%d: %v — skipping", issue.Number, err)
			continue
		}
		log.Printf("✅ Commented on issue #%d", issue.Number)

		// Step 5: Log to CSV
		entry := LogEntry{
			IssueURL:    issue.HTMLURL,
			IssueTitle:  issue.Title,
			IssueType:   issueType,
			CommentBody: comment,
			CommentedAt: time.Now(),
		}
		if err := LogComment(entry); err != nil {
			log.Printf("log issue #%d: %v", issue.Number, err)
		}

		commented++

		// Small delay between comments to avoid rate limiting
		time.Sleep(2 * time.Second)
	}

	log.Printf("Done. Commented on %d issues. Log saved to %s", commented, logFile)
}

// mustEnv reads a required environment variable or exits.
func mustEnv(key string) string {
	val := os.Getenv(key)
	if val == "" {
		fmt.Fprintf(os.Stderr, "Error: environment variable %s is required\n", key)
		os.Exit(1)
	}
	return val
}
