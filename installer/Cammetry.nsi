Unicode true

!include "MUI2.nsh"
!include "WinMessages.nsh"

!define APP_NAME "Cammetry"
!define APP_VERSION "0.6.0-beta"
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

VIProductVersion "0.6.0.0"
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

; Check the process image rather than relying on the window title. This works
; even if a clip changes the caption or setup is upgrading an older Cammetry.
Function EnsureCammetryClosed
ensure_check_process:
  nsExec::ExecToStack '"$SYSDIR\tasklist.exe" /FI "IMAGENAME eq ${APP_EXE}" /NH'
  Pop $0
  Pop $1
  StrCpy $2 $1 12
  StrCmp $2 "${APP_EXE}" ensure_running ensure_done

ensure_running:
  MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION \
    "${APP_NAME} is currently running.$\r$\n$\r$\nIt must be closed before setup can continue. Click OK to close it now. Any active playback or export will stop." \
    IDOK ensure_close IDCANCEL ensure_abort

ensure_close:
  FindWindow $3 "" "${APP_NAME} ${APP_VERSION}"
  StrCmp $3 0 +3
  SendMessage $3 ${WM_CLOSE} 0 0
  Sleep 1000
  nsExec::ExecToStack '"$SYSDIR\taskkill.exe" /T /IM "${APP_EXE}"'
  Pop $4
  Pop $5
  Sleep 700
  nsExec::ExecToStack '"$SYSDIR\tasklist.exe" /FI "IMAGENAME eq ${APP_EXE}" /NH'
  Pop $4
  Pop $5
  StrCpy $6 $5 12
  StrCmp $6 "${APP_EXE}" ensure_force ensure_done

ensure_force:
  nsExec::ExecToStack '"$SYSDIR\taskkill.exe" /F /T /IM "${APP_EXE}"'
  Pop $4
  Pop $5
  Sleep 350
  Goto ensure_check_process

ensure_abort:
  Abort

ensure_done:
  Return
FunctionEnd

Function un.EnsureCammetryClosed
un_check_process:
  nsExec::ExecToStack '"$SYSDIR\tasklist.exe" /FI "IMAGENAME eq ${APP_EXE}" /NH'
  Pop $0
  Pop $1
  StrCpy $2 $1 12
  StrCmp $2 "${APP_EXE}" un_running un_done

un_running:
  MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION \
    "${APP_NAME} is currently running.$\r$\n$\r$\nIt must be closed before uninstalling. Click OK to close it now. Any active playback or export will stop." \
    IDOK un_close IDCANCEL un_abort

un_close:
  FindWindow $3 "" "${APP_NAME} ${APP_VERSION}"
  StrCmp $3 0 +3
  SendMessage $3 ${WM_CLOSE} 0 0
  Sleep 1000
  nsExec::ExecToStack '"$SYSDIR\taskkill.exe" /T /IM "${APP_EXE}"'
  Pop $4
  Pop $5
  Sleep 700
  nsExec::ExecToStack '"$SYSDIR\tasklist.exe" /FI "IMAGENAME eq ${APP_EXE}" /NH'
  Pop $4
  Pop $5
  StrCpy $6 $5 12
  StrCmp $6 "${APP_EXE}" un_force un_done

un_force:
  nsExec::ExecToStack '"$SYSDIR\taskkill.exe" /F /T /IM "${APP_EXE}"'
  Pop $4
  Pop $5
  Sleep 350
  Goto un_check_process

un_abort:
  Abort

un_done:
  Return
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

; MUI localizes the installer chrome. Keep these two component descriptions as
; an explicit English fallback in every bundled installer language so no page
; has a missing string and makensis /WX remains warning-free.
LangString DESC_SecMain ${LANG_ENGLISH} "Installs Cammetry and its bundled local video-processing components."
LangString DESC_SecDesktop ${LANG_ENGLISH} "Creates a shortcut on the desktop."
LangString DESC_SecMain ${LANG_SPANISH} "Installs Cammetry and its bundled local video-processing components."
LangString DESC_SecDesktop ${LANG_SPANISH} "Creates a shortcut on the desktop."
LangString DESC_SecMain ${LANG_FRENCH} "Installs Cammetry and its bundled local video-processing components."
LangString DESC_SecDesktop ${LANG_FRENCH} "Creates a shortcut on the desktop."
LangString DESC_SecMain ${LANG_GERMAN} "Installs Cammetry and its bundled local video-processing components."
LangString DESC_SecDesktop ${LANG_GERMAN} "Creates a shortcut on the desktop."
LangString DESC_SecMain ${LANG_SIMPCHINESE} "Installs Cammetry and its bundled local video-processing components."
LangString DESC_SecDesktop ${LANG_SIMPCHINESE} "Creates a shortcut on the desktop."
LangString DESC_SecMain ${LANG_JAPANESE} "Installs Cammetry and its bundled local video-processing components."
LangString DESC_SecDesktop ${LANG_JAPANESE} "Creates a shortcut on the desktop."
LangString DESC_SecMain ${LANG_KOREAN} "Installs Cammetry and its bundled local video-processing components."
LangString DESC_SecDesktop ${LANG_KOREAN} "Creates a shortcut on the desktop."
LangString DESC_SecMain ${LANG_PORTUGUESE} "Installs Cammetry and its bundled local video-processing components."
LangString DESC_SecDesktop ${LANG_PORTUGUESE} "Creates a shortcut on the desktop."
LangString DESC_SecMain ${LANG_RUSSIAN} "Installs Cammetry and its bundled local video-processing components."
LangString DESC_SecDesktop ${LANG_RUSSIAN} "Creates a shortcut on the desktop."
LangString DESC_SecMain ${LANG_ITALIAN} "Installs Cammetry and its bundled local video-processing components."
LangString DESC_SecDesktop ${LANG_ITALIAN} "Creates a shortcut on the desktop."
LangString DESC_SecMain ${LANG_DUTCH} "Installs Cammetry and its bundled local video-processing components."
LangString DESC_SecDesktop ${LANG_DUTCH} "Creates a shortcut on the desktop."
LangString DESC_SecMain ${LANG_POLISH} "Installs Cammetry and its bundled local video-processing components."
LangString DESC_SecDesktop ${LANG_POLISH} "Creates a shortcut on the desktop."
LangString DESC_SecMain ${LANG_TURKISH} "Installs Cammetry and its bundled local video-processing components."
LangString DESC_SecDesktop ${LANG_TURKISH} "Creates a shortcut on the desktop."

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
  RMDir /r /REBOOTOK "$INSTDIR"
SectionEnd
