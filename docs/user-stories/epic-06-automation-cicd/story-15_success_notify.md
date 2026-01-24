# Story 15: Success Notifications

**Story ID**: epic-06-story-15  
**Epic**: Epic 06 - Automation & CI/CD  
**Priority**: Low  
**Estimate**: 1 hour  
**Status**: Not Started

## User Story

**As a** project user  
**I want** to be notified when a new release is available  
**So that** I can download the latest wiki archive

## Acceptance Criteria

1. **Release Announcement**
   - [ ] Post to Discord/Slack on successful release
   - [ ] Include release statistics
   - [ ] Link to GitHub release page
   - [ ] Format as announcement

2. **RSS Feed**
   - [ ] GitHub releases RSS feed available
   - [ ] Feed includes release notes
   - [ ] Feed auto-generated
   - [ ] Documented for users

3. **Optional Notifications**
   - [ ] Success notifications configurable
   - [ ] Can be disabled for scheduled runs
   - [ ] Always enabled for manual runs
   - [ ] Separate channel from errors

4. **Content**
   - [ ] Release version and date
   - [ ] Summary of changes
   - [ ] Download links
   - [ ] Statistics (pages, revisions, files)

## Technical Details

### Discord Success Notification

```yaml
- name: Send success notification
  if: success()
  uses: sarisia/actions-status-discord@v1
  with:
    webhook: ${{ secrets.DISCORD_WEBHOOK_ANNOUNCE }}
    status: "success"
    title: "✅ New iRO Wiki Archive Released!"
    description: |
      **Version:** ${{ steps.version.outputs.release_version }}
      **Date:** ${{ steps.version.outputs.release_date }}
      
      **Statistics:**
      - 📄 Pages: ${{ steps.stats.outputs.page_count }}
      - 📝 Revisions: ${{ steps.stats.outputs.revision_count }}
      - 📁 Files: ${{ steps.stats.outputs.file_count }}
      
      [📥 Download Release](${{ steps.create-release.outputs.url }})
    color: 0x00ff00
    username: "iRO Wiki Archive Bot"
```

### Slack Success Notification

```yaml
- name: Announce release on Slack
  if: success()
  uses: slackapi/slack-github-action@v1
  with:
    payload: |
      {
        "text": "✅ New iRO Wiki Archive Available!",
        "blocks": [
          {
            "type": "header",
            "text": {
              "type": "plain_text",
              "text": "🎉 New Archive Released"
            }
          },
          {
            "type": "section",
            "fields": [
              {
                "type": "mrkdwn",
                "text": "*Version:*\n${{ steps.version.outputs.release_version }}"
              },
              {
                "type": "mrkdwn",
                "text": "*Date:*\n${{ steps.version.outputs.release_date }}"
              }
            ]
          },
          {
            "type": "section",
            "text": {
              "type": "mrkdwn",
              "text": "*Statistics:*\n• Pages: ${{ steps.stats.outputs.page_count }}\n• Revisions: ${{ steps.stats.outputs.revision_count }}\n• Files: ${{ steps.stats.outputs.file_count }}"
            }
          },
          {
            "type": "actions",
            "elements": [
              {
                "type": "button",
                "text": {
                  "type": "plain_text",
                  "text": "Download Release"
                },
                "url": "${{ steps.create-release.outputs.url }}",
                "style": "primary"
              }
            ]
          }
        ]
      }
  env:
    SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_ANNOUNCE }}
```

### Conditional Success Notification

```yaml
- name: Determine if should announce
  id: should-announce
  if: success()
  run: |
    # Always announce scheduled runs (monthly releases)
    if [[ "${{ github.event_name }}" == "schedule" ]]; then
      echo "announce=true" >> $GITHUB_OUTPUT
      exit 0
    fi
    
    # Announce manual runs only if explicitly requested
    if [[ "${{ github.event.inputs.announce }}" == "true" ]]; then
      echo "announce=true" >> $GITHUB_OUTPUT
    else
      echo "announce=false" >> $GITHUB_OUTPUT
    fi

- name: Announce release
  if: success() && steps.should-announce.outputs.announce == 'true'
  # ... notification steps
```

### RSS Feed Documentation

```markdown
# Subscribe to Releases

## GitHub Releases RSS

Subscribe to automatic release notifications:

```
https://github.com/OWNER/REPO/releases.atom
```

## Discord Bot

Join our Discord server for instant notifications:
[Discord Invite Link]

## Email Notifications

Watch the repository on GitHub and enable release notifications:
1. Click "Watch" at top of repository
2. Select "Custom"
3. Check "Releases"
```

### Twitter/Mastodon Announcement

```yaml
- name: Post to Twitter
  if: success() && steps.should-announce.outputs.announce == 'true'
  run: |
    # Using Twitter API v2
    curl -X POST "https://api.twitter.com/2/tweets" \
      -H "Authorization: Bearer ${{ secrets.TWITTER_BEARER_TOKEN }}" \
      -H "Content-Type: application/json" \
      -d @- <<EOF
    {
      "text": "🎉 New iRO Wiki Archive Released!\n\nVersion: ${{ steps.version.outputs.release_version }}\n📄 ${{ steps.stats.outputs.page_count }} pages\n📝 ${{ steps.stats.outputs.revision_count }} revisions\n\n${{ steps.create-release.outputs.url }}"
    }
    EOF
```

## Dependencies

- **Story 04**: Generate statistics (for notification content)
- **Story 06**: Create GitHub release (for release URL)

## Implementation Notes

- Use separate webhook for announcements vs errors
- Keep success notifications concise
- Include actionable links (download)
- GitHub RSS feed is automatic
- Consider announcement frequency (monthly is good)
- Test notifications before going live
- Success notifications are optional

## Testing Requirements

- [ ] Test Discord announcement
- [ ] Test Slack announcement
- [ ] Test conditional logic
- [ ] Verify links work
- [ ] Test formatting looks good
- [ ] Test with real release
- [ ] Verify RSS feed works
- [ ] Test disabling announcements

## Definition of Done

- [ ] Success notification implemented
- [ ] Conditional logic implemented
- [ ] RSS feed documented
- [ ] Announcement content finalized
- [ ] Tested with real release
- [ ] Documentation updated
- [ ] Code reviewed and approved
