# Story 14: Failure Notifications

**Story ID**: epic-06-story-14  
**Epic**: Epic 06 - Automation & CI/CD  
**Priority**: Medium  
**Estimate**: 2 hours  
**Status**: Not Started

## User Story

**As a** project maintainer  
**I want** to receive notifications when workflows fail  
**So that** I can quickly respond to scrape failures or CI issues

## Acceptance Criteria

1. **Email Notifications**
   - [ ] Email sent on workflow failure
   - [ ] Email includes error details
   - [ ] Email includes workflow run link
   - [ ] Configurable recipient list

2. **Discord/Slack Integration**
   - [ ] Post to Discord/Slack channel on failure
   - [ ] Include formatted error message
   - [ ] Link to workflow run and logs
   - [ ] Tag relevant team members

3. **Notification Content**
   - [ ] Workflow name and result
   - [ ] Error message summary
   - [ ] Failed job/step name
   - [ ] Timestamp and duration
   - [ ] Direct link to logs

4. **Smart Notifications**
   - [ ] Only notify on persistent failures (not transient)
   - [ ] Rate limiting for repeated failures
   - [ ] Different severity levels
   - [ ] Digest mode for multiple failures

## Technical Details

### Email Notification (GitHub Default)

```yaml
# GitHub sends email notifications automatically for:
# - Workflow failures on main branch
# - Workflow failures you triggered
# Configure in: github.com/settings/notifications
```

### Discord Webhook Notification

```yaml
- name: Send Discord notification on failure
  if: failure()
  uses: sarisia/actions-status-discord@v1
  with:
    webhook: ${{ secrets.DISCORD_WEBHOOK }}
    status: ${{ job.status }}
    title: "Monthly Scrape Failed"
    description: |
      The monthly wiki scrape has failed.
      
      **Workflow:** ${{ github.workflow }}
      **Job:** ${{ github.job }}
      **Run:** [${{ github.run_number }}](${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }})
      
      Please check the logs for details.
    color: 0xff0000
    username: "iRO Wiki Scraper"
    avatar_url: "https://github.com/actions.png"
```

### Slack Notification

```yaml
- name: Send Slack notification on failure
  if: failure()
  uses: slackapi/slack-github-action@v1
  with:
    payload: |
      {
        "text": "❌ Monthly Scrape Failed",
        "blocks": [
          {
            "type": "header",
            "text": {
              "type": "plain_text",
              "text": "❌ Workflow Failed"
            }
          },
          {
            "type": "section",
            "fields": [
              {
                "type": "mrkdwn",
                "text": "*Workflow:*\n${{ github.workflow }}"
              },
              {
                "type": "mrkdwn",
                "text": "*Repository:*\n${{ github.repository }}"
              },
              {
                "type": "mrkdwn",
                "text": "*Branch:*\n${{ github.ref_name }}"
              },
              {
                "type": "mrkdwn",
                "text": "*Triggered by:*\n${{ github.actor }}"
              }
            ]
          },
          {
            "type": "section",
            "text": {
              "type": "mrkdwn",
              "text": "<${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}|View Workflow Run>"
            }
          }
        ]
      }
  env:
    SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

### Custom Email Notification

```yaml
- name: Send email notification
  if: failure()
  uses: dawidd6/action-send-mail@v3
  with:
    server_address: smtp.gmail.com
    server_port: 465
    username: ${{ secrets.MAIL_USERNAME }}
    password: ${{ secrets.MAIL_PASSWORD }}
    subject: "❌ iRO Wiki Scrape Failed - ${{ github.run_number }}"
    to: maintainers@example.com
    from: GitHub Actions
    html_body: |
      <h2>Workflow Failed</h2>
      <p><strong>Repository:</strong> ${{ github.repository }}</p>
      <p><strong>Workflow:</strong> ${{ github.workflow }}</p>
      <p><strong>Run Number:</strong> ${{ github.run_number }}</p>
      <p><strong>Triggered by:</strong> ${{ github.actor }}</p>
      <p><strong>Time:</strong> ${{ github.event.head_commit.timestamp }}</p>
      
      <h3>Error Details</h3>
      <p>The workflow failed during execution. Please check the logs for details.</p>
      
      <a href="${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}">
        View Workflow Run
      </a>
```

### Extract Error Details

```yaml
- name: Extract error information
  if: failure()
  id: error-info
  run: |
    # Get failed step name
    FAILED_STEP="${{ github.job }}"
    
    # Get error from logs (last 20 lines)
    ERROR_MSG=$(tail -n 20 ${{ github.workspace }}/.github/workflows/*.log 2>/dev/null || echo "No detailed error available")
    
    # Sanitize for JSON
    ERROR_MSG=$(echo "$ERROR_MSG" | jq -Rs .)
    
    echo "failed_step=$FAILED_STEP" >> $GITHUB_OUTPUT
    echo "error_message=$ERROR_MSG" >> $GITHUB_OUTPUT

- name: Notify with error details
  if: failure()
  run: |
    curl -X POST "${{ secrets.DISCORD_WEBHOOK }}" \
      -H "Content-Type: application/json" \
      -d @- <<EOF
    {
      "content": "@here Monthly scrape failed!",
      "embeds": [{
        "title": "❌ Workflow Failed",
        "color": 15158332,
        "fields": [
          {
            "name": "Failed Step",
            "value": "${{ steps.error-info.outputs.failed_step }}"
          },
          {
            "name": "Error",
            "value": "\`\`\`${{ steps.error-info.outputs.error_message }}\`\`\`"
          },
          {
            "name": "Logs",
            "value": "[View Run](${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }})"
          }
        ],
        "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      }]
    }
    EOF
```

### Conditional Notifications

```yaml
- name: Check if should notify
  if: failure()
  id: should-notify
  run: |
    # Only notify for main branch failures
    if [[ "${{ github.ref }}" == "refs/heads/main" ]]; then
      echo "notify=true" >> $GITHUB_OUTPUT
    else
      echo "notify=false" >> $GITHUB_OUTPUT
    fi
    
    # Don't notify for manual workflow failures (testing)
    if [[ "${{ github.event_name }}" == "workflow_dispatch" ]]; then
      echo "notify=false" >> $GITHUB_OUTPUT
    fi

- name: Send notification
  if: failure() && steps.should-notify.outputs.notify == 'true'
  uses: sarisia/actions-status-discord@v1
  with:
    webhook: ${{ secrets.DISCORD_WEBHOOK }}
```

### GitHub Issues on Failure

```yaml
- name: Create issue on failure
  if: failure() && github.ref == 'refs/heads/main'
  uses: actions/github-script@v7
  with:
    script: |
      const issue = await github.rest.issues.create({
        owner: context.repo.owner,
        repo: context.repo.repo,
        title: `Workflow failed: ${context.workflow} #${context.runNumber}`,
        body: `## Workflow Failure\n\n` +
              `**Workflow:** ${context.workflow}\n` +
              `**Run:** [#${context.runNumber}](${context.payload.repository.html_url}/actions/runs/${context.runId})\n` +
              `**Triggered by:** @${context.actor}\n` +
              `**Branch:** ${context.ref}\n\n` +
              `Please investigate the failure and take appropriate action.`,
        labels: ['bug', 'ci-failure', 'automated']
      });
      
      console.log(`Created issue #${issue.data.number}`);
```

## Dependencies

- **Story 01**: Scheduled workflow trigger (workflow to notify about)

## Implementation Notes

- GitHub's default email notifications work well
- Discord/Slack webhooks are easy to set up
- Store webhook URLs in repository secrets
- Consider rate limiting for repeated failures
- Include actionable information in notifications
- Test notifications with intentional failures
- Consider time zones for @mentions
- Webhook URLs should be kept secret

## Testing Requirements

- [ ] Test Discord webhook with failure
- [ ] Test Slack webhook with failure
- [ ] Test email notification
- [ ] Test error extraction works
- [ ] Test conditional notification logic
- [ ] Verify links in notifications work
- [ ] Test notification formatting
- [ ] Test with different failure scenarios

## Definition of Done

- [ ] Discord notification implemented
- [ ] Email notification configured (optional)
- [ ] Slack notification implemented (optional)
- [ ] Error extraction implemented
- [ ] Conditional logic implemented
- [ ] Webhook secrets configured
- [ ] Tested with intentional failure
- [ ] Documentation updated
- [ ] Code reviewed and approved
