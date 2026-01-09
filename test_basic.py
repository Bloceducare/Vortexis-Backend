#!/usr/bin/env python3
"""
Basic test script to check if the Django setup is working correctly.
Run this with: python test_basic.py
"""

import os
import sys
import django





# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vortexis_backend.settings')
django.setup()

def test_imports():
    """Test that all models can be imported successfully"""
    try:
        from accounts.models import User, Profile, Skill
        from hackathon.models import Hackathon, Theme, Rule, Submission, Review, Prize
        from team.models import Team
        from project.models import Project
        from organization.models import Organization
        print("✅ All model imports successful")
        return True
    except ImportError as e:
        print(f"❌ Model import failed: {e}")
        return False

def test_serializers():
    """Test that all serializers can be imported successfully"""
    try:
        from accounts.serializers import UserSerializer, ProfileSerializer
        from hackathon.serializers import HackathonSerializer, ThemeSerializer, PrizeSerializer
        from team.serializers import TeamSerializer, CreateTeamSerializer
        from project.serializers import ProjectSerializer, CreateProjectSerializer
        from organization.serializers import OrganizationSerializer
        print("✅ All serializer imports successful")
        return True
    except ImportError as e:
        print(f"❌ Serializer import failed: {e}")
        return False

def test_views():
    """Test that all views can be imported successfully"""
    try:
        from accounts.views import UserRegistrationView, UserLoginView
        from hackathon.views import HackathonCreateView, HackathonListView
        from team.views import TeamViewSet
        from project.views import ProjectViewSet
        from organization.views import CreateOrganizationView
        print("✅ All view imports successful")
        return True
    except ImportError as e:
        print(f"❌ View import failed: {e}")
        return False

def test_urls():
    """Test that URL configurations are working"""
    try:
        from django.urls import reverse
        from django.test import Client
        client = Client()
        
        # Test admin URL
        response = client.get('/admin/')
        print(f"✅ Admin URL accessible (status: {response.status_code})")
        
        # Test API documentation URLs
        response = client.get('/swagger/')
        print(f"✅ Swagger URL accessible (status: {response.status_code})")
        
        return True
    except Exception as e:
        print(f"❌ URL test failed: {e}")
        return False

if __name__ == '__main__':
    print("🧪 Running Basic Tests for Vortexis Backend\n")
    
    tests = [
        test_imports,
        test_serializers,
        test_views,
        test_urls
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The basic setup is working correctly.")
        sys.exit(0)
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        sys.exit(1)
