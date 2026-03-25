#!/bin/bash
set -e

echo "📦 Installing OpenClaw..."
npm install -g openclaw@latest

echo "✅ OpenClaw installed. Version:"
openclaw --version

echo "📁 Creating config directories..."
mkdir -p ~/.openclaw/workspace
mkdir -p ~/.openclaw/skills

echo "🎉 Setup complete! Run 'openclaw onboard' to configure."
