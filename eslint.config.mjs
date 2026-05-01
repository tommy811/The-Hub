import nextVitals from "eslint-config-next/core-web-vitals"

const config = [
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "out/**",
      "supabase/**",
      "scripts/**",
      "docs/**",
      "00-Meta/**",
      "01-Product/**",
      "02-Architecture/**",
      "03-Database/**",
      "04-Pipeline/**",
      "05-Prompts/**",
      "06-Sessions/**",
    ],
  },
  ...nextVitals,
  {
    files: ["src/**/*.{ts,tsx}"],
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-unused-vars": [
        "warn",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
        },
      ],
    },
  },
]

export default config
