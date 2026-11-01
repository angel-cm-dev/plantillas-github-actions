'use strict';

/**
 * Convierte un texto en un slug apto para URLs: minúsculas, sin tildes ni símbolos.
 * @param {string} text
 * @returns {string}
 */
function slugify(text) {
  return String(text ?? '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

module.exports = { slugify };
