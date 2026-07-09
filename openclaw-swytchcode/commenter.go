// Package main provides GitHub commenting for the GitHub triage bot.
// All GitHub API calls go through swytchcode exec — the correct execution layer.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os/exec"
	"strings"
	"time"
)

// GitHubIssue represents a GitHub issue returned by the API.
type GitHubIssue struct {
	Number  int    `json:"number"`
	Title   string `json:"title"`
	Body    string `json:"body"`
	HTMLURL string `json:"html_url"`
	State   string `json:"state"`
}

// swytchcodeExecResponse is the normalized JSON response from swytchcode exec --json.
type swytchcodeExecResponse struct {
	StatusCode int             `json:"status_code"`
	Data       json.RawMessage `json:"data"`
}

// execViaSwytchcode calls swytchcode exec --json with args passed via JSON stdin.
// This follows the exact pattern from swytchcode docs.
func execViaSwytchcode(ctx context.Context, canonicalID string, args map[string]interface{}) (json.RawMessage, error) {
	inputJSON, err := json.Marshal(args)
	if err != nil {
		return nil, fmt.Errorf("marshal swytchcode input: %w", err)
	}

	cmd := exec.CommandContext(ctx, "swytchcode", "exec", "--json", canonicalID)
	cmd.Stdin = strings.NewReader(string(inputJSON))

	out, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("swytchcode exec %s: %w", canonicalID, err)
	}

	var resp swytchcodeExecResponse
	if err := json.Unmarshal(out, &resp); err != nil {
		return nil, fmt.Errorf("parse swytchcode response for %s: %w", canonicalID, err)
	}

	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("swytchcode exec %s: API returned %d: %s", canonicalID, resp.StatusCode, resp.Data)
	}

	return resp.Data, nil
}

// GitHubCommenter posts comments on GitHub issues via swytchcode exec.
type GitHubCommenter struct {
	token string
}

// NewGitHubCommenter creates a new commenter with the given GitHub PAT.
func NewGitHubCommenter(token string) *GitHubCommenter {
	return &GitHubCommenter{token: token}
}

// PostComment posts a comment on the given issue via swytchcode exec repos.issue.comments.create.
func (c *GitHubCommenter) PostComment(ctx context.Context, owner, repo string, issueNumber int, body string) error {
	_, err := execViaSwytchcode(ctx, "repos.issue.comments.create", map[string]interface{}{
		"owner":        owner,
		"repo":         repo,
		"issue_number": fmt.Sprintf("%d", issueNumber),
		"Authorization": "Bearer " + c.token,
		"body": map[string]string{
			"body": body,
		},
	})
	if err != nil {
		return fmt.Errorf("post comment on issue #%d: %w", issueNumber, err)
	}
	return nil
}

// FetchIssues fetches open issues from the given repo via swytchcode exec repos.issue.get.
func FetchIssues(ctx context.Context, token, owner, repo string) ([]GitHubIssue, error) {
	// Add timeout for the swytchcode call
	ctx, cancel := context.WithTimeout(ctx, 30*time.Second)
	defer cancel()

	data, err := execViaSwytchcode(ctx, "repos.issue.get", map[string]interface{}{
		"owner":         owner,
		"repo":          repo,
		"Authorization": "Bearer " + token,
	})
	if err != nil {
		return nil, fmt.Errorf("fetch issues: %w", err)
	}

	var issues []GitHubIssue
	if err := json.Unmarshal(data, &issues); err != nil {
		return nil, fmt.Errorf("decode issues: %w", err)
	}

	return issues, nil
}
