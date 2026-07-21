const OIDC_ENV_VARS = ["AUTH_SECRET", "OIDC_ISSUER", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET"] as const;

function presentVars(env: NodeJS.ProcessEnv = process.env) {
  return OIDC_ENV_VARS.filter((name) => Boolean(env[name]));
}

export function isOidcConfigured(env: NodeJS.ProcessEnv = process.env) {
  return presentVars(env).length === OIDC_ENV_VARS.length;
}

export function isOidcPartiallyConfigured(env: NodeJS.ProcessEnv = process.env) {
  const present = presentVars(env).length;
  return present > 0 && present < OIDC_ENV_VARS.length;
}

export function missingOidcVars(env: NodeJS.ProcessEnv = process.env) {
  return OIDC_ENV_VARS.filter((name) => !env[name]);
}

export function getRequiredGroup(env: NodeJS.ProcessEnv = process.env) {
  return env.OIDC_REQUIRED_GROUP;
}

export function getGroupsClaimName(env: NodeJS.ProcessEnv = process.env) {
  return env.OIDC_GROUPS_CLAIM || "groups";
}

export function hasRequiredGroup(claimValue: unknown, requiredGroup: string): boolean {
  if (Array.isArray(claimValue)) {
    return claimValue.includes(requiredGroup);
  }

  if (typeof claimValue === "string") {
    return claimValue.split(/\s+/).includes(requiredGroup);
  }

  return false;
}
