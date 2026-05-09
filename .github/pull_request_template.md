# Pull Request

## Description

<!-- Provide a clear and concise description of what this PR accomplishes -->

## Type of Change

<!-- Mark the relevant option with an "x" -->

- [ ] 🐛 Bug fix (non-breaking change which fixes an issue)
- [ ] ✨ New feature (non-breaking change which adds functionality)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] 📚 Documentation update
- [ ] 🔧 Maintenance (dependency updates, code cleanup, etc.)
- [ ] 🚀 Performance improvement
- [ ] 🔒 Security enhancement
- [ ] 🧪 Test coverage improvement

## Related Issues

<!-- Link to related issues using "Fixes #123", "Closes #456", "Relates to #789" -->

## Changes Made

<!-- Describe the specific changes made in this PR -->

- Change 1
- Change 2
- Change 3

## Component/Area

<!-- Mark all that apply -->

- [ ] Backend (Django/Python)
- [ ] Frontend (HTML/CSS/JS)
- [ ] API (DRF endpoints)
- [ ] Database (models/migrations)
- [ ] Authentication/Security
- [ ] Tests
- [ ] Documentation
- [ ] CI/CD
- [ ] Docker/Deployment

## Healthcare/Clinical Context

<!-- If applicable, describe the healthcare context and benefits -->

**Use Case**: <!-- e.g., Clinical audit, Patient surveys, Research data collection -->

**Benefit**: <!-- How does this help healthcare professionals or patients? -->

## Security Considerations

<!-- Mark if applicable and provide details -->

- [ ] No security impact
- [ ] Security improvement
- [ ] Requires security review
- [ ] Changes authentication/authorization
- [ ] Modifies data encryption/handling
- [ ] Updates audit logging

**Details**: <!-- Describe any security implications -->

## Breaking Changes

<!-- If this introduces breaking changes, describe them and provide migration instructions -->

- [ ] No breaking changes
- [ ] Breaking changes (see details below)

**Migration Notes**: <!-- How should users adapt to these changes? -->

## Testing

<!-- Describe how this has been tested -->

- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed
- [ ] Tested with healthcare use cases
- [ ] Tested on hosted environment
- [ ] Tested with self-hosted deployment

**Test Summary**: <!-- Describe your testing approach and results -->

## Performance Impact

- [ ] No performance impact
- [ ] Performance improvement
- [ ] Potential performance regression (justified below)

**Details**: <!-- Explain any performance considerations -->

## Documentation

- [ ] No documentation needed
- [ ] Documentation updated in this PR
- [ ] Documentation update needed (separate PR/issue)
- [ ] API documentation updated
- [ ] User guide updated

## Deployment Notes

<!-- Any special considerations for deployment -->

- [ ] No special deployment considerations
- [ ] Requires database migration
- [ ] Requires environment variable changes
- [ ] Requires new dependencies
- [ ] Requires configuration changes

**Notes**: <!-- Describe deployment requirements -->

## Pre-submission Checklist

<!-- Ensure all items are completed before requesting review -->

### Code Quality

- [ ] Code follows the project's coding standards (ruff/black/isort)
- [ ] Self-review completed
- [ ] Code is well-documented with comments where needed
- [ ] No debugging code or console logs left in

### Test Coverage

- [ ] All existing tests pass locally
- [ ] New tests added for new functionality
- [ ] Tests cover edge cases and error conditions
- [ ] Manual testing completed

### Security & Compliance

- [ ] No secrets or sensitive data committed
- [ ] Dummy data used in tests follows guidelines (non-realistic patterns)
- [ ] Healthcare data handling follows established patterns
- [ ] GDPR/privacy considerations addressed if applicable

### Documentation & Communication

- [ ] CONTRIBUTING.md guidelines followed
- [ ] Commit messages are clear and descriptive
- [ ] Related issues linked
- [ ] Breaking changes documented
- [ ] Version bump considered (`pyproject.toml`) and release impact assessed

### Project Specific

- [ ] Works with both hosted and self-hosted deployments
- [ ] Maintains backward compatibility with existing surveys
- [ ] Preserves audit trail functionality
- [ ] Healthcare use cases considered

## Screenshots/Videos

<!-- If applicable, add screenshots or videos demonstrating the changes -->

## Additional Notes

<!-- Any additional information for reviewers -->

---

**For Reviewers**:

- Check that healthcare context is appropriate
- Verify security considerations are addressed
- Ensure changes work for both hosted and self-hosted users
- Validate that clinical workflows remain intuitive
