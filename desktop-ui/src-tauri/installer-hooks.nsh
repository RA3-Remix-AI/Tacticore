!macro NSIS_HOOK_PREINSTALL
!ifdef TACTICORE_GUARD_BINARY
  ; Read original ledgers using this installer's pinned verifier before any
  ; installed file is replaced. An older client's projection may be defective.
  InitPluginsDir
  ClearErrors
  SetOutPath "$PLUGINSDIR\TacticoreGuard"
  File /oname=tacticore-desktop.exe "${TACTICORE_GUARD_BINARY}"
  SetOutPath "$PLUGINSDIR\TacticoreGuard\runtime"
  File /r "${TACTICORE_GUARD_RUNTIME}\*"
  IfErrors tacticore_install_blocked
  nsExec::ExecToStack '"$PLUGINSDIR\TacticoreGuard\tacticore-desktop.exe" --prepare-update'
!else
  IfFileExists "$INSTDIR\tacticore-desktop.exe" 0 tacticore_install_clear
  nsExec::ExecToStack '"$INSTDIR\tacticore-desktop.exe" --prepare-update'
!endif
  Pop $0
  Pop $1
  StrCmp $0 "0" tacticore_install_clear
  tacticore_install_blocked:
  MessageBox MB_OK|MB_ICONEXCLAMATION "Stop the commander, wait for independent return, then exit the game before updating. Unverified history blocks installation. No application files were replaced."
  Abort
  tacticore_install_clear:
  SetOutPath "$INSTDIR"
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  IfFileExists "$INSTDIR\tacticore-desktop.exe" 0 tacticore_uninstall_clear
  nsExec::ExecToStack '"$INSTDIR\tacticore-desktop.exe" --prepare-update'
  Pop $0
  Pop $1
  StrCmp $0 "0" tacticore_uninstall_clear
  MessageBox MB_OK|MB_ICONEXCLAMATION "Stop the commander and wait for independent return before uninstalling. User settings, credentials, game and Mod files are retained."
  Abort
  tacticore_uninstall_clear:
!macroend
