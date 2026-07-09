// Package main provides issue classification for the GitHub triage bot.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os/exec"
	"strings"
)

// classifyIssue sends the issue title and body to Claude via swytchcode MCP
// and returns the issue type: setup, error, webhook, or unknown.
func classifyIssue(ctx context.Context, title, body string) (IssueType, error) {
	prompt := fmt.Sprintf(`You are classifying a GitHub issue about Stripe integration.

Classify this issue into exactly one of these categories:
- setup     → user is asking how to set up or install Stripe
- error     → user is getting an error, bug, or unexpected behaviour
- webhook   → user is asking about Stripe webhooks specifically
- unknown   → does not fit any of the above

Reply with a single word only: setup, error, webhook, or unknown.

Issue title: %s
Issue body: %s`, title, body)

	// Call Claude via swytchcode MCP exec
	// swytchcode_exec calls the MCP tool directly as a subprocess
	args := []string{"exec", "--json", "swytchcode_exec"}
	input := map[string]interface{}{
		"tool": "swytchcode_discover",
		"args": map[string]string{
			"query": prompt,
		},
	}

	inputJSON, err := json.Marshal(input)
	if err != nil {
		return IssueTypeUnknown, fmt.Errorf("marshal classifier input: %w", err)
	}

	cmd := exec.CommandContext(ctx, "swytchcode", args...)
	cmd.Stdin = strings.NewReader(string(inputJSON))

	out, err := cmd.Output()
	if err != nil {
		// Fallback: classify locally using simple keyword matching
		return classifyLocally(title, body), nil
	}

	result := strings.TrimSpace(strings.ToLower(string(out)))

	switch {
	case strings.Contains(result, "setup"):
		return IssueTypeSetup, nil
	case strings.Contains(result, "error"):
		return IssueTypeError, nil
	case strings.Contains(result, "webhook"):
		return IssueTypeWebhook, nil
	default:
		return IssueTypeUnknown, nil
	}
}

// classifyLocally is a keyword-based fallback classifier.
// Used when the swytchcode MCP call fails.
func classifyLocally(title, body string) IssueType {
	text := strings.ToLower(title + " " + body)

	webhookKeywords := []string{"webhook", "event", "listener", "endpoint", "notify"}
	for _, kw := range webhookKeywords {
		if strings.Contains(text, kw) {
			return IssueTypeWebhook
		}
	}

	errorKeywords := []string{"error", "fail", "exception", "401", "403", "404", "500", "crash", "bug", "broken", "not working"}
	for _, kw := range errorKeywords {
		if strings.Contains(text, kw) {
			return IssueTypeError
		}
	}

	setupKeywords := []string{"how", "setup", "install", "integrate", "start", "begin", "getting started", "configure"}
	for _, kw := range setupKeywords {
		if strings.Contains(text, kw) {
			return IssueTypeSetup
		}
	}

	return IssueTypeUnknown
}
