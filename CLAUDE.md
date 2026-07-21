# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**fedora-policy-generator** is a web-based generator for creating Firefox policies. The tool enables users to generate policy configurations through an interactive web interface.

## Technology Stack

This project currently follows the JavaScript/TypeScript ecosystem for web development. Once initialized, the tech stack will likely include:
- Frontend framework (React or similar)
- Build tooling (Webpack/Vite/Next.js)
- Policy generation/validation logic
- Firefox policy schema handling

## Architecture Guidance

When developing this generator, consider these architectural principles:

1. **Policy Generation Engine**: Core logic to validate and serialize Firefox policies into consumable formats (JSON/XML)
2. **Web UI Layer**: Interactive interface for users to configure policies without manual editing
3. **Schema Handling**: Firefox policy schema definitions (from Mozilla's official documentation) as the source of truth
4. **Export/Download**: Mechanisms to download generated policies in appropriate formats

## Development Commands

Once the project is initialized, these commands will be commonly used:

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Run tests (single test: npm test -- path/to/test.js)
npm test

# Lint code
npm run lint

# Type check (if TypeScript is used)
npm run type-check
```

## Key Concepts

- **Firefox Policies**: Understand the structure of Firefox group policies (Group Policy Objects for Windows, configuration for macOS/Linux)
- **Policy Schema**: Mozilla provides a formal schema for policies; this generator should validate against it
- **User Experience**: The main value is reducing complexity—users should be able to generate correct policies without deep Firefox policy knowledge

## Important Notes

- Ensure generated policies are always valid according to Mozilla's Firefox policy schema
- Test generated policies against actual Firefox installations when possible
- Keep policy schema definitions in sync with Mozilla's official documentation
- Consider different deployment targets (Windows GPO, macOS MDM, Linux managed systems)

## Repository Branches

Work on feature branches (`claude/*` for Claude-driven development) and create pull requests for review before merging to main.
