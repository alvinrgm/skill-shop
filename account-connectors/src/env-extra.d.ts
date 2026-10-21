// Secrets (set with `wrangler secret put NAME`) are not in wrangler.jsonc, so
// `wrangler types` cannot see them. Declare them here. Every one except the
// Google sign-in trio and the allowlist is optional: a vendor's tools register
// only when its secrets are present. Typed as string for simplicity; an unset
// secret is undefined at runtime, and the code checks before using it.
declare global {
	interface Env {
		// Required: per-user Google sign-in
		GOOGLE_CLIENT_ID: string;
		GOOGLE_CLIENT_SECRET: string;
		COOKIE_ENCRYPTION_KEY: string;
		// Required: who may sign in (set at least one; comma-separated)
		ALLOWED_EMAILS: string;
		ALLOWED_DOMAINS: string;
		// Recommended: public base URL of this deployment, no trailing slash
		WORKER_BASE: string;
		// Optional: the one admin email (google_api passthrough, delegated approval slips)
		ADMIN_EMAIL: string;
		// Optional vendor: Meta reads (System User token)
		META_ACCESS_TOKEN: string;
		// Optional vendor: Meta writes (per-user Facebook Login)
		META_APP_ID: string;
		META_APP_SECRET: string;
		// Optional vendor: Google Ads reads
		GOOGLE_ADS_CLIENT_ID: string;
		GOOGLE_ADS_CLIENT_SECRET: string;
		GOOGLE_ADS_DEVELOPER_TOKEN: string;
		GOOGLE_ADS_REFRESH_TOKEN: string;
		GOOGLE_ADS_LOGIN_CUSTOMER_ID: string;
		// Optional vendor: Shopify reads
		SHOPIFY_CLIENT_ID: string;
		SHOPIFY_CLIENT_SECRET: string;
		SHOPIFY_TOKENS: string;
		// Optional vendor: Klaviyo reads
		KLAVIYO_API_KEY: string;
	}
}
export {};
