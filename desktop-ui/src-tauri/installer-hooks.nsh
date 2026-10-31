!macro NSIS_HOOK_PREINSTALL
  IfFileExists "$INSTDIR\tacticore-desktop.exe" 0 tacticore_install_clear
  nsExec::ExecToStack '"$INSTDIR\tacticore-desktop.exe" --prepare-update'
  Pop $0
  Pop $1
  StrCmp $0 "0" tacticore_install_clear
  MessageBox MB_OK|MB_ICONEXCLAMATION "Tacticore has an active or unverified commander. Stop it in the current client and wait for independent return before updating. No files were replaced."
  Abort
  tacticore_install_clear:
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
