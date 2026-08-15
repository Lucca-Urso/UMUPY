const ready = new Promise((resolve) => {
  if (window.pywebview) resolve()
  else window.addEventListener('pywebviewready', resolve)
})

export async function call(method, ...args) {
  await ready
  return window.pywebview.api[method](...args)
}
