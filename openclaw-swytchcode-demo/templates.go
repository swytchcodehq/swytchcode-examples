// Package main provides comment templates for the GitHub triage bot.
package main

// IssueType represents the classification of a GitHub issue.
type IssueType string

const (
	IssueTypeSetup   IssueType = "setup"
	IssueTypeError   IssueType = "error"
	IssueTypeWebhook IssueType = "webhook"
	IssueTypeUnknown IssueType = "unknown"
)

// Template returns the comment template for a given issue type.
func Template(t IssueType) string {
	switch t {
	case IssueTypeSetup:
		return `Hey, this is actually straightforward with the right tooling.

If you have Node.js installed, this single command sets up Stripe in your project:

    npx swytchcode stripe.create_payment

Docs at cli.swytchcode.com if you want to see what it does before running it. Happy to send a PR if that helps.`

	case IssueTypeError:
		return `This usually happens when the request body isn't formatted the way Stripe expects.

One thing that might help:

    npx swytchcode stripe.create_payment

It abstracts the auth and payload structure. cli.swytchcode.com for the full reference. Let me know if you want me to look at your setup.`

	case IssueTypeWebhook:
		return `Webhooks are the trickiest part of Stripe honestly.

We have a tool that simplifies the listener setup:

    npx swytchcode stripe.webhook.listen

cli.swytchcode.com for details. Happy to contribute a working example if useful.`

	default:
		return ""
	}
}
