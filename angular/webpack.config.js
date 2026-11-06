const glob = require('glob');
const { PurgeCSSPlugin } = require("purgecss-webpack-plugin");

// Bootstrap 5 still uses Sass features that Dart Sass has deprecated (@import, global built-ins, ...).
// Those warnings come from node_modules, so silence them instead of flooding the build output.
function silenceBootstrapDeprecations(rules) {
  for (const rule of rules || []) {
    for (const entry of [].concat(rule.use || [])) {
      if (entry && typeof entry === 'object' && /sass-loader/.test(entry.loader || '')) {
        entry.options = entry.options || {};
        entry.options.sassOptions = {
          ...entry.options.sassOptions,
          quietDeps: true,
          silenceDeprecations: ['import', 'global-builtin', 'color-functions', 'if-function']
        };
      }
    }
    silenceBootstrapDeprecations(rule.rules);
    silenceBootstrapDeprecations(rule.oneOf);
  }
}

module.exports = (config) => {
  silenceBootstrapDeprecations(config.module.rules);
  config.plugins.push(
    new PurgeCSSPlugin({
      // Components may also have inline templates, so scan the .ts files as well
      paths: glob.sync('./src/**/*.{html,ts}', { nodir: true }),
      safelist: {
        deep: [
          /offcanvas-/,
          /tooltip-/,
          /tooltip/,
          /modal/,
          /modal-/,
          /toast-/,
          /toast/,
          /show/,
          /fade/,
          /end-/,
          /position-/,
          /p-/,
          /d-/,
          /top-/,
          /bg-/,
          /text-/
        ]
      }
    })
  );
  return config;
};
