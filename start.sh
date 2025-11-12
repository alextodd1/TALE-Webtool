#!/bin/bash

# TALE Pair Finder - Startup Script
# This script helps you quickly start the application

set -e

echo "================================================"
echo "  TALE Pair Finder - Startup Script"
echo "================================================"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed."
    echo "Please install Docker first:"
    echo "  sudo apt update"
    echo "  sudo apt install docker.io docker-compose"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Error: Docker Compose is not installed."
    echo "Please install Docker Compose first:"
    echo "  sudo apt install docker-compose"
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  Warning: .env file not found. Creating from .env.example..."
    cp .env.example .env
    echo "✅ Created .env file. Please review and update if needed."
fi

echo "🚀 Starting TALE Pair Finder..."
echo ""

# Stop any existing containers
echo "📦 Stopping existing containers..."
docker-compose down

echo ""
echo "🔨 Building and starting services..."
docker-compose up -d --build

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check if services are running
if docker-compose ps | grep -q "Up"; then
    echo ""
    echo "================================================"
    echo "  ✅ TALE Pair Finder is now running!"
    echo "================================================"
    echo ""
    echo "🌐 Access the application at:"
    echo "   http://localhost:8000"
    echo ""
    echo "🔍 API Health Check:"
    echo "   http://localhost:8000/api/health"
    echo ""
    echo "📊 View logs:"
    echo "   docker-compose logs -f"
    echo ""
    echo "🛑 Stop the application:"
    echo "   docker-compose down"
    echo ""
    echo "================================================"
else
    echo ""
    echo "❌ Error: Services failed to start properly."
    echo "Check logs with: docker-compose logs"
    exit 1
fi
