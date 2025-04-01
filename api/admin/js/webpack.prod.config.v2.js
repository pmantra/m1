const webpack = require('webpack');
const path = require('path');
const sass = require('sass');

module.exports = {
  resolve: {
    extensions: ['.js', '.jsx'],
  },
  entry: ['babel-polyfill', './index.js'],
  output: {
    libraryTarget: 'var',
    library: 'AdminTool',
    path: path.resolve(__dirname, '../static/js'),
    filename: 'app-min-v2.js',
  },
  cache: false,
  module: {
    rules: [
      {
        test: /\.(js|jsx)$/,
        loader: 'babel-loader',
        include: __dirname,
      },
      {
        test: /\.json$/,
        loader: 'json-loader',
      },
      {
        test: /\.css$/,
        loader: 'style-loader!css-loader',
      },
      {
        test: /\.scss$/,
        use: [
          'style-loader',
          'css-loader',
          {
            loader: 'sass-loader',
            options: {
              implementation: sass,
            },
          },
        ],
      },
      {
        test: /\.(ttf|otf|eot|svg)(\?v=[0-9]\.[0-9]\.[0-9])?|(jpg|gif)$/,
        loader: 'file-loader',
      },
      {
        test: /\.woff($|\?)|\.woff2($|\?)/,
        loader: 'url-loader',
      },
    ],
  },
  plugins: [
    new webpack.ProvidePlugin({
      $: 'jquery',
      jQuery: 'jquery',
    }),
    new webpack.optimize.UglifyJsPlugin({
      compress: {
        warnings: false,
      },
    }),
    new webpack.DefinePlugin({
      'process.env': {
        NODE_ENV: JSON.stringify('production'),
      },
    }),
    new webpack.BannerPlugin({
      banner: `[hash].[name]`,
      entryOnly: true,
    }),
  ],
};
