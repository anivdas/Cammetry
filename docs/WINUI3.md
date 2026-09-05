# Windows UI architecture

## Current status

Cammetry v0.5.1 is a Python/Tkinter application. Windows DWM backdrop calls and
custom Fluent-styled widgets improve its appearance, but they do not make it a
WinUI 3 application.

The `windows/Cammetry.WinUI` project is the native Windows shell under active
development for Cammetry 0.6. It is a real C#/XAML WinUI 3 application using the
Windows App SDK. It currently provides the navigation shell, native Mica
backdrop, folder picker, startup health state, and a local process bridge to the
existing Cammetry core.

## Why a bridge

The existing parser, SEI telemetry decoder, clip discovery, local library,
incident packaging, event detection, playback, and FFmpeg export code are
already testable Python services. Rewriting those components simultaneously
with the UI would create unnecessary regression risk.

The bridge therefore:

- communicates through line-delimited JSON over stdin/stdout;
- binds no TCP port and starts no network listener;
- requires no Tesla or Cammetry account;
- keeps video and telemetry processing local;
- can be packaged as `Cammetry.Core.exe` for release builds;
- allows the existing Tkinter application to remain available on macOS/Linux.

## Migration gates

The WinUI shell becomes the default Windows release only after it supports:

1. synchronized multi-camera playback and seeking;
2. the continuous event timeline and trim markers;
3. live telemetry, map, and review-marker updates;
4. export configuration, progress, cancellation, and fallback errors;
5. Local Library and Incident Workspace workflows;
6. accessibility, keyboard, scaling, high-contrast, and reduced-motion tests;
7. installer and portable-package smoke tests on Windows 10 and Windows 11.

Until those gates pass, the Python UI remains the production Windows interface.

## Development prerequisites

- Windows 10 version 1809 or newer
- Visual Studio 2026 with the WinUI application development workload
- .NET 10 SDK
- Developer Mode

Open `windows/Cammetry.WinUI/Cammetry.WinUI.csproj` and build the x64 target.
During development the shell starts `cammetry_bridge.py` from the repository;
packaged builds will place a PyInstaller-built `Cammetry.Core.exe` beside the
WinUI executable.
