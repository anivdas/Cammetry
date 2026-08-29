Unicode true

!include "MUI2.nsh"
!include "WinMessages.nsh"

!define APP_NAME "Cammetry"
!define APP_VERSION "0.5.0"
!define APP_EXE "Cammetry.exe"
!define APP_DIR "Cammetry"
!define APP_REGKEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\Cammetry"

Name "${APP_NAME} ${APP_VERSION}"
OutFile "..\release\Cammetry-Setup-v${APP_VERSION}.exe"
InstallDir "$PROGRAMFILES64\${APP_DIR}"
RequestExecutionLevel admin
SetCompressor /SOLID lzma
SetCompressorDictSize 64
Icon "..\assets\app.ico"
UninstallIcon "..\assets\app.ico"
BrandingText "Cammetry - free open source"

VIProductVersion "0.5.0.0"
VIAddVersionKey "ProductName" "${APP_NAME}"
VIAddVersionKey "ProductVersion" "${APP_VERSION}"
VIAddVersionKey "FileVersion" "${APP_VERSION}"
VIAddVersionKey "FileDescription" "Installer for ${APP_NAME}"
VIAddVersionKey "LegalCopyright" "Copyright (c) 2026 Cammetry contributors"

!define MUI_LANGDLL_REGISTRY_ROOT HKLM
!define MUI_LANGDLL_REGISTRY_KEY "Software\Cammetry"
!define MUI_LANGDLL_REGISTRY_VALUENAME "Installer Language"

!define MUI_ABORTWARNING
!define MUI_ICON "..\assets\app.ico"
!define MUI_UNICON "..\assets\app.ico"
!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "Launch Cammetry"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "Spanish"
!insertmacro MUI_LANGUAGE "French"
!insertmacro MUI_LANGUAGE "German"
!insertmacro MUI_LANGUAGE "SimpChinese"
!insertmacro MUI_LANGUAGE "Japanese"
!insertmacro MUI_LANGUAGE "Korean"
!insertmacro MUI_LANGUAGE "Portuguese"
!insertmacro MUI_LANGUAGE "Russian"
!insertmacro MUI_LANGUAGE "Italian"
!insertmacro MUI_LANGUAGE "Dutch"
!insertmacro MUI_LANGUAGE "Polish"
!insertmacro MUI_LANGUAGE "Turkish"

!insertmacro MUI_RESERVEFILE_LANGDLL

; Close a currently installed Cammetry instance before replacing files.
; We first ask the visible application to close normally, then use taskkill only
; as a safety net so upgrades cannot leave locked files behind.
Function EnsureCammetryClosed
  ReadRegStr $0 HKLM "${APP_REGKEY}" "DisplayVersion"
  StrCmp $0 "" ensure_force_cleanup
  FindWindow $1 "" "${APP_NAME} $0"
  StrCmp $1 0 ensure_force_cleanup

  MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION \
    "${APP_NAME} $0 is currently running.$\r$\n$\r$\nIt must be closed before setup can continue. Click OK to close it now. Any active playback or export will stop." \
    IDOK ensure_close_window IDCANCEL ensure_abort

ensure_close_window:
  SendMessage $1 ${WM_CLOSE} 0 0
  Sleep 1200

ensure_force_cleanup:
  ; Harmless when the process is not running. This also catches a hidden or
  ; orphaned Cammetry process that no longer has a normal main window.
  nsExec::ExecToStack '"$SYSDIR\taskkill.exe" /F /T /IM "${APP_EXE}"'
  Pop $2
  Pop $3
  Sleep 350
  Return

ensure_abort:
  Abort
FunctionEnd

; Uninstaller equivalent. The exact current-version title lets us warn the user
; before closing the app, then taskkill guarantees the install tree is unlocked.
Function un.EnsureCammetryClosed
  FindWindow $0 "" "${APP_NAME} ${APP_VERSION}"
  StrCmp $0 0 un_force_cleanup

  MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION \
    "${APP_NAME} is currently running.$\r$\n$\r$\nIt must be closed before uninstalling. Click OK to close it now. Any active playback or export will stop." \
    IDOK un_close_window IDCANCEL un_abort

un_close_window:
  SendMessage $0 ${WM_CLOSE} 0 0
  Sleep 1200

un_force_cleanup:
  nsExec::ExecToStack '"$SYSDIR\taskkill.exe" /F /T /IM "${APP_EXE}"'
  Pop $1
  Pop $2
  Sleep 350
  Return

un_abort:
  Abort
FunctionEnd

Function .onInit
  SetShellVarContext all
  SetRegView 64
  Call EnsureCammetryClosed
  !insertmacro MUI_LANGDLL_DISPLAY
FunctionEnd

Function un.onInit
  SetShellVarContext all
  SetRegView 64
  !insertmacro MUI_UNGETLANGUAGE
  Call un.EnsureCammetryClosed
FunctionEnd

Section "Cammetry" SecMain
  SectionIn RO
  SetOutPath "$INSTDIR"
  File /r "..\dist-installer\Cammetry\*.*"

  CreateDirectory "$SMPROGRAMS\${APP_DIR}"
  CreateShortcut "$SMPROGRAMS\${APP_DIR}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
  CreateShortcut "$SMPROGRAMS\${APP_DIR}\Uninstall ${APP_NAME}.lnk" "$INSTDIR\Uninstall.exe"

  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "${APP_REGKEY}" "DisplayName" "${APP_NAME}"
  WriteRegStr HKLM "${APP_REGKEY}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKLM "${APP_REGKEY}" "Publisher" "Cammetry Project"
  WriteRegStr HKLM "${APP_REGKEY}" "DisplayIcon" "$INSTDIR\${APP_EXE}"
  WriteRegStr HKLM "${APP_REGKEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKLM "${APP_REGKEY}" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
  WriteRegDWORD HKLM "${APP_REGKEY}" "NoModify" 1
  WriteRegDWORD HKLM "${APP_REGKEY}" "NoRepair" 1
SectionEnd

Section /o "Desktop shortcut" SecDesktop
  CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
SectionEnd

LangString DESC_SecMain ${LANG_ENGLISH} "Installs Cammetry and its bundled local video-processing components."
LangString DESC_SecDesktop ${LANG_ENGLISH} "Creates a shortcut on the desktop."

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecMain} $(DESC_SecMain)
  !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} $(DESC_SecDesktop)
!insertmacro MUI_FUNCTION_DESCRIPTION_END

Section "Uninstall"
  Delete "$DESKTOP\${APP_NAME}.lnk"
  Delete "$SMPROGRAMS\${APP_DIR}\${APP_NAME}.lnk"
  Delete "$SMPROGRAMS\${APP_DIR}\Uninstall ${APP_NAME}.lnk"
  RMDir "$SMPROGRAMS\${APP_DIR}"
  DeleteRegKey HKLM "${APP_REGKEY}"
  DeleteRegKey HKLM "Software\Cammetry"

  ; The running app has already been closed in un.onInit. Remove immediately;
  ; /REBOOTOK is only a final safety net for an unexpected external file lock.
  RMDir /r /REBOOTOK "$INSTDIR"
SectionEnd
