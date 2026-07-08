import { defineConfig } from 'vitest/config';

export default defineConfig({
    test: {
        environment: 'jsdom',
        coverage: {
            provider: 'v8',
            reporter: ['text', 'lcov'],
            // static/dist are build output, not source; node_modules is a
            // dependency - none of these are meaningful for coverage.
            exclude: ['static/**', 'dist/**', 'node_modules/**', '**/*.test.js'],
        },
    },
});
