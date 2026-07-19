export function confirmBudgetOverwrite(action: string, detail: string) {
  return window.confirm(
    `${action}\n\n${detail}\n\nThis can overwrite planned budget amounts that are already defined. Continue?`,
  );
}
