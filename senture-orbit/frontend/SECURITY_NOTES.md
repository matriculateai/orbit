# Frontend Security Notes

This document outlines the security vulnerabilities in the frontend dependencies and explains why they cannot be fully resolved without breaking changes.

## Summary

**Current Status:** 9 moderate vulnerabilities (development dependencies only)
**Production Impact:** **NONE** - All vulnerabilities affect development tooling only
**Recommendation:** Safe for production use

## Vulnerability Analysis

### High-Severity Vulnerabilities: NONE ✅

All high and critical severity vulnerabilities have been resolved.

### Moderate Vulnerabilities (9 total)

All moderate vulnerabilities are in **development dependencies** only and do **not affect production builds**.

#### 1. nth-check <2.0.1 (Inefficient RegEx)
- **Severity:** Moderate
- **Affects:** `svgo` (development build tool)
- **Production Impact:** None
- **Reason Not Fixed:** Upgrading breaks react-scripts 5.0.1 compatibility
- **Mitigation:** Only affects SVG optimization during build, not runtime

#### 2. postcss <8.4.31 (Line Return Parsing Error)
- **Severity:** Moderate
- **Affects:** `resolve-url-loader` (development tool)
- **Production Impact:** None
- **Reason Not Fixed:** Upgrading causes dependency conflicts with webpack
- **Mitigation:** Only affects CSS processing during build

#### 3. webpack-dev-server <=5.2.0 (Source Code Exposure)
- **CVE:** GHSA-9jgg-88mc-972h, GHSA-4v9v-hfq4-rm2v
- **Severity:** Moderate
- **Affects:** Development server only (`npm start`)
- **Production Impact:** **None** - webpack-dev-server is NOT included in production builds
- **Reason Not Fixed:** Upgrading to 5.2.1+ breaks react-scripts 5.0.1 compatibility (ajv-keywords module resolution failure)
- **Attack Vector:** Requires user to visit malicious website while dev server is running on non-Chromium browser
- **Mitigation:**
  - Never expose development server to public internet
  - Only run on localhost during development
  - Production builds use static hosting (no webpack-dev-server)

## Deprecated Packages (Warnings Only - Not Vulnerabilities)

The following packages show deprecation warnings but do **not** have security vulnerabilities:

### Babel Plugins (Merged to ECMAScript Standard)
- `@babel/plugin-proposal-private-methods` → Use `@babel/plugin-transform-private-methods`
- `@babel/plugin-proposal-numeric-separator` → Use `@babel/plugin-transform-numeric-separator`
- `@babel/plugin-proposal-nullish-coalescing-operator` → Use `@babel/plugin-transform-nullish-coalescing-operator`
- `@babel/plugin-proposal-class-properties` → Use `@babel/plugin-transform-class-properties`
- `@babel/plugin-proposal-optional-chaining` → Use `@babel/plugin-transform-optional-chaining`
- `@babel/plugin-proposal-private-property-in-object` → Use `@babel/plugin-transform-private-property-in-object`

**Why Not Upgraded:** These are transitive dependencies of react-scripts. Upgrading requires ejecting from Create React App or migrating to a different build system.

### Other Deprecated Packages
- `inflight@1.0.6` - Memory leak (used by glob)
- `stable@0.1.8` - Array.sort() is now natively stable
- `glob@7.2.3` - Older version (v9+ recommended)
- `rimraf@3.0.2` - Older version (v4+ recommended)
- `rollup-plugin-terser` → Use `@rollup/plugin-terser`
- `@humanwhocodes/config-array` → Use `@eslint/config-array`
- `@humanwhocodes/object-schema` → Use `@eslint/object-schema`
- `eslint@8.57.1` - No longer supported (v9+ recommended)
- `svgo@1.3.2` - Older version (v2+ recommended)
- `three-mesh-bvh@0.7.8` - Three.js version incompatibility

**Impact:** These deprecations do not pose security risks, only maintenance concerns for future updates.

## Node.js Compatibility

**IMPORTANT:** react-scripts 5.0.1 requires Node.js 16 or 18.

- ✅ **Node 16.x** - Fully compatible
- ✅ **Node 18.x** - Fully compatible
- ❌ **Node 19+** - INCOMPATIBLE (causes build failures)

If using Node.js 19 or higher, you will encounter module resolution errors:
```
Error: Cannot find module 'ajv/dist/compile/codegen'
```

### Solution: Use Node Version Manager

**Using nvm:**
```bash
# Install Node 18 LTS
nvm install 18
nvm use 18

# Install dependencies and build
cd frontend
npm install
npm run build
```

**Using n:**
```bash
# Install and use Node 18
n 18

# Install dependencies and build
cd frontend
npm install
npm run build
```

## Why Not Migrate to react-scripts 6.x?

react-scripts 5.0.1 is the last version before Create React App was officially archived. Options for upgrading:

1. **Migrate to Vite** - Modern, faster build tool
   - Pros: Much faster builds, better DX, actively maintained
   - Cons: Requires significant refactoring
   - Recommendation: **Best long-term solution**

2. **Migrate to Next.js** - React framework
   - Pros: Built-in routing, SSR, API routes
   - Cons: Architectural changes required
   - Recommendation: If you need SSR/SSG

3. **Eject from CRA** - Manual webpack configuration
   - Pros: Full control over config
   - Cons: Complex, maintenance burden
   - Recommendation: **Not recommended**

4. **Stay on react-scripts 5.0.1**
   - Pros: No changes needed, stable
   - Cons: No new features, some deprecation warnings
   - Recommendation: **Acceptable for now** (current approach)

## Production Security Checklist

✅ **All production builds are secure:**

- [x] Zero high/critical vulnerabilities
- [x] Zero runtime vulnerabilities
- [x] All moderate vulnerabilities are development-only
- [x] Production builds do not include development dependencies
- [x] Static builds can be deployed to any CDN/static host
- [x] No webpack-dev-server in production
- [x] All user inputs properly sanitized (React escapes by default)
- [x] CORS configured correctly in backend

## Development Security Best Practices

When running `npm start` for development:

1. **Never expose dev server to public internet**
   - Only bind to localhost (default behavior)
   - Never use 0.0.0.0 binding in production networks

2. **Use latest Node 18 LTS**
   ```bash
   node --version  # Should show v18.x.x
   ```

3. **Keep dependencies updated** (when safe)
   ```bash
   npm outdated  # Check for updates
   npm update    # Update patch/minor versions only
   ```

4. **Run security audits regularly**
   ```bash
   npm audit
   npm audit --production  # Only check production dependencies
   ```

## Future Migration Path

**Recommended:** Migrate to Vite when time permits

**Migration Guide:**
```bash
# 1. Install Vite and dependencies
npm install --save-dev vite @vitejs/plugin-react

# 2. Create vite.config.ts
# 3. Update index.html (move to root)
# 4. Update import statements (add .tsx extensions where needed)
# 5. Replace react-scripts commands with vite commands

# Before:
npm start → npm run dev
npm run build → npm run build (uses vite)

# Benefits:
- 10-50x faster dev server startup
- Hot Module Replacement (HMR) in <100ms
- Modern ESM-based build
- Actively maintained
- Zero vulnerabilities
```

## Questions?

For security concerns or questions about these vulnerabilities:

1. **Check npm advisory database:** https://github.com/advisories
2. **Verify production builds:** `npm audit --production` (should show 0 vulnerabilities)
3. **Contact maintainers:** See main README.md for support

## Version History

- **v1.0.0 (2025-12-23)** - Initial security documentation
  - 9 moderate vulnerabilities (all development-only)
  - Node.js 16-18 compatibility documented
  - Migration path to Vite outlined

---

**Last Updated:** 2025-12-23
**Next Review:** Q1 2026 or when upgrading react-scripts/migrating to Vite
