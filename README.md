<picture>
	<source media="(prefers-color-scheme: dark)" srcset="checktick_app/static/icons/CheckTick_long-03-dark.svg">
	<source media="(prefers-color-scheme: light)" srcset="checktick_app/static/icons/CheckTick_long-03.svg">
	<img alt="CheckTick" src="checktick_app/static/icons/CheckTick_long-03.svg">
</picture>

![Version](https://img.shields.io/badge/version-0.4.6-5fcfdd?style=for-the-badge)
![GitHub License](https://img.shields.io/github/license/eatyourpeas/checktick?style=for-the-badge&color=5fcfdd)
![OpenAPI](https://img.shields.io/badge/OpenAPI-3.0-5fcfdd?style=for-the-badge&logo=openapiinitiative&logoColor=white)
![GitHub Issues or Pull Requests](https://img.shields.io/github/issues/eatyourpeas/checktick?style=for-the-badge&color=5fcfdd)
[![Docker Image](https://img.shields.io/badge/docker-ghcr.io-5fcfdd?style=for-the-badge&logo=docker&logoColor=white)](https://github.com/eatyourpeas/checktick/pkgs/container/checktick)
[![Uptime](https://app.statuscake.com/button/index.php?Track=7928755&Days=7&Design=1)](https://app.statuscake.com/UptimeStatus.php?tid=7928755)

CheckTick is an open source secure survey platform for medical audit and research, created for the NHS. Features include:

- **Survey Creation**: Survey creators build questions from a library of question types, either as drag and drop in a builder, or they can import them written in markdown. Users can also create surveys using natural language and the LLM will generate the markdown.
- **Security**: All data and AI hosted on secure servers in the UK. Every survey encrypted by default with AES-256-GCM, Role-based access control, audit logs, and single sign-on, GDPR, NHS DSPT, and Caldicott compliant. It has been penetration tested.
- **Language Support**: Surveys can be published in a range of languages for multilingual audiences, using an LLM.
- **Publication**: Fully controlled by the survey creator including access (open links vs login required for sensitive data)
- **Datasets**: There is a growing library of standardised lists taken from the NHS Data Dictionary (eg blood groups, ethniticities) and trusted NHS sources (eg hospital lists) to populate dropdowns for which contributions are welcome.
- **Question Bank**: Survey questions can be shared with others to reuse or within teams (depending on account). Validated open questionaires (eg PHQ-9) can be imported into surveys without having to re-enter the questions.
- **Customisable**: platform styling and survey styling are supported. Patient facing surveys are WCAG AA compliant. Tools are included to test accessibilty of custom styles prior to publishing. NHS styling for surveys is supported.
- There is also an API with limited endpoints (largely due to security posture).

Try it out [here](https://checktick.uk)
>[!NOTE]
>This is in a sandbox dev environment and is for demo purposes only. Do not store patient or sensitive information here.

## Documentation

- Users and implementers: [checktick.uk/docs](https://checktick.uk/docs)
- Developer/maintainer references: [docs/README.md](docs/README.md)
- Agent workflow guidance: [AGENTS.md](AGENTS.md)

## 🐳 Self-Hosting

CheckTick can be self-hosted using Docker. Pre-built multi-architecture images are available on GitHub Container Registry.

### Quick Start

```bash
# Download docker-compose file
wget https://raw.githubusercontent.com/eatyourpeas/checktick/main/docker-compose.registry.yml

# Configure environment
cp .env.selfhost .env
# Edit .env with your settings

# Start CheckTick
docker compose -f docker-compose.registry.yml up -d
```

**📦 Docker Images:** [ghcr.io/eatyourpeas/checktick](https://github.com/eatyourpeas/checktick/pkgs/container/checktick)

**📚 Full Documentation:** See [Self-Hosting Guides](https://checktick.eatyourpeas.dev/docs/self-hosting-quickstart/)

## Versioning & Deployment

For release, container tags, and publish trigger rules, see [docs/versioning-and-deployment.md](docs/versioning-and-deployment.md).

## Getting Help & Contributing

### 💬 Community & Support

- **[Discussions](https://github.com/eatyourpeas/checktick/discussions)** - For questions, ideas, and community support
- **[Issues](https://github.com/eatyourpeas/checktick/issues)** - For bug reports and specific feature requests
- **[Documentation](https://checktick.eatyourpeas.dev/docs/)** - Complete guides and API documentation

### When to use what?

**Use Discussions for:**

- General questions about using CheckTick
- Seeking advice on healthcare survey design
- Sharing your CheckTick use cases
- Community announcements and updates
- Brainstorming new ideas before formal feature requests
- Getting help with deployment or configuration
- Asking "How do I...?" questions

**Use Issues for:**

- Reporting bugs or unexpected behavior
- Requesting specific features with detailed requirements
- Documentation corrections or improvements
- Security concerns (non-sensitive)

### Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines on contributing code, documentation, and reporting issues.
