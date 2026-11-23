// Applies the saved theme before first paint to avoid a light/dark flash.
(function () {
  try {
    var theme = JSON.parse(localStorage.getItem('dimora.theme'));
    if (theme === 'light' || theme === 'dark') document.documentElement.dataset.theme = theme;
  } catch (error) {
    /* storage unavailable: follow the system theme */
  }
})();
