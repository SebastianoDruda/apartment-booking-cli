"use strict";

const byId = (id) => document.getElementById(id);
let operations = [];
let selected;
let lastResponse = "";

function requestDetails() {
  let path = selected.path;
  const query = new URLSearchParams();
  for (const parameter of selected.operation.parameters || []) {
    const input = byId(`parameter-${parameter.in}-${parameter.name}`);
    if (parameter.in === "path")
      path = path.replace(
        `{${parameter.name}}`,
        encodeURIComponent(input.value),
      );
    else query.set(parameter.name, input.value);
  }
  const url = new URL(path, window.location.origin);
  url.search = query.toString();
  return {
    url,
    body: selected.operation.requestBody
      ? byId("request-body").value
      : undefined,
  };
}

function shellQuote(value) {
  return "'" + value.replaceAll("'", "'\\''") + "'";
}

function updateCurl() {
  const { url, body } = requestDetails();
  const command = ["curl -i", "-X " + selected.method, shellQuote(url.href)];
  if (body !== undefined)
    command.push(
      "-H 'Content-Type: application/json'",
      "--data-raw " + shellQuote(body),
    );
  byId("curl-example").textContent = command.join(" \\\n  ");
}

function selectOperation(index) {
  selected = operations[index];
  document.querySelectorAll(".operation").forEach((button, i) => {
    button.classList.toggle("active", i === index);
    button.setAttribute("aria-pressed", String(i === index));
  });
  byId("operation-title").textContent = selected.operation.summary;
  byId("operation-tag").textContent = selected.operation.tags[0];
  byId("operation-description").textContent =
    selected.method === "GET"
      ? "Read-only request. This operation does not change booking records."
      : "This request changes stored data. Review the values before sending.";
  byId("method").textContent = selected.method;
  byId("method").className = "method " + selected.method.toLowerCase();
  byId("endpoint").textContent = selected.path;
  byId("send-request").firstChild.textContent = "Send " + selected.method + " ";
  byId("parameters").replaceChildren();
  for (const parameter of selected.operation.parameters || []) {
    const wrapper = document.createElement("div");
    wrapper.className = "parameter";
    const label = document.createElement("label");
    label.className = "field-label";
    label.textContent = parameter.name;
    const tag = document.createElement("span");
    tag.textContent = parameter.in + " · required";
    label.append(tag);
    const input = document.createElement("input");
    input.id = `parameter-${parameter.in}-${parameter.name}`;
    label.htmlFor = input.id;
    input.value = parameter.schema.example;
    input.required = true;
    input.addEventListener("input", updateCurl);
    wrapper.append(label, input);
    if (parameter.schema.description) {
      const hint = document.createElement("p");
      hint.className = "hint";
      hint.textContent = parameter.schema.description;
      wrapper.append(hint);
    }
    byId("parameters").append(wrapper);
  }
  byId("body-section").hidden = !selected.operation.requestBody;
  if (selected.operation.requestBody) {
    byId("request-body").value = JSON.stringify(
      selected.operation.requestBody.content["application/json"].example,
      null,
      2,
    );
  }
  updateCurl();
}

async function sendRequest(event) {
  event.preventDefault();
  const { url, body } = requestDetails();
  const method = selected.method;
  byId("send-request").disabled = true;
  byId("response-status").textContent = "Sending…";
  byId("response-status").className = "";
  const started = performance.now();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    if (body !== undefined) {
      const parsed = JSON.parse(body);
      if (
        parsed === null ||
        Array.isArray(parsed) ||
        typeof parsed !== "object"
      )
        throw new Error("The JSON body must be an object.");
    }
    const response = await fetch(url, {
      method,
      body,
      signal: controller.signal,
      headers: body !== undefined ? { "Content-Type": "application/json" } : {},
      cache: "no-store",
    });
    const text = await response.text();
    try {
      lastResponse = JSON.stringify(JSON.parse(text), null, 2);
    } catch {
      lastResponse = text;
    }
    byId("response-status").textContent =
      `${response.status} ${response.statusText}`;
    byId("response-status").className = response.ok ? "success" : "failure";
    byId("response-time").textContent =
      `${method} · ${Math.round(performance.now() - started)} ms`;
  } catch (error) {
    lastResponse =
      error.name === "AbortError"
        ? "The request timed out after 15 seconds."
        : error.message;
    byId("response-status").textContent = "Request not completed";
    byId("response-status").className = "failure";
    byId("response-time").textContent =
      "Check the request and server connection.";
  } finally {
    clearTimeout(timeout);
    byId("response-body").textContent = lastResponse;
    byId("copy-response").disabled = false;
    byId("send-request").disabled = false;
  }
}

async function copyText(button, text) {
  const label = button.textContent;
  try {
    await navigator.clipboard.writeText(text);
    button.textContent = "Copied";
  } catch {
    button.textContent = "Select the text to copy";
  }
  setTimeout(() => {
    button.textContent = label;
  }, 1800);
}

async function initialize() {
  byId("server-origin").textContent = window.location.origin;
  try {
    const response = await fetch("/api/openapi.json");
    if (!response.ok) throw new Error("Could not load the API specification.");
    const spec = await response.json();
    operations = Object.entries(spec.paths).flatMap(([path, methods]) =>
      Object.entries(methods).map(([method, operation]) => ({
        path,
        method: method.toUpperCase(),
        operation,
      })),
    );
    const groups = ["Overview", "Apartments", "Bookings", "Availability"];
    const methods = ["GET", "POST", "PATCH", "DELETE"];
    operations.sort(
      (a, b) =>
        groups.indexOf(a.operation.tags[0]) -
          groups.indexOf(b.operation.tags[0]) ||
        methods.indexOf(a.method) - methods.indexOf(b.method),
    );
    const navigation = byId("operations");
    navigation.replaceChildren();
    let group;
    operations.forEach((item, index) => {
      if (group !== item.operation.tags[0]) {
        group = item.operation.tags[0];
        const heading = document.createElement("h3");
        heading.textContent = group;
        navigation.append(heading);
      }
      const button = document.createElement("button");
      button.type = "button";
      button.className = "operation";
      const method = document.createElement("span");
      method.className = "method " + item.method.toLowerCase();
      method.textContent = item.method;
      const label = document.createElement("span");
      label.textContent = item.operation.summary;
      button.append(method, label);
      button.addEventListener("click", () => selectOperation(index));
      navigation.append(button);
    });
    byId("request-form").addEventListener("submit", sendRequest);
    byId("reset-example").addEventListener("click", () =>
      selectOperation(operations.indexOf(selected)),
    );
    byId("request-body").addEventListener("input", updateCurl);
    byId("copy-curl").addEventListener("click", (event) =>
      copyText(event.target, byId("curl-example").textContent),
    );
    byId("copy-response").addEventListener("click", (event) =>
      copyText(event.target, lastResponse),
    );
    selectOperation(
      operations.findIndex((item) => item.path === "/api/health"),
    );
  } catch (error) {
    byId("page-error").hidden = false;
    byId("page-error").textContent =
      error.message + " Reload this page after checking the server.";
    byId("send-request").disabled = true;
  }
}

initialize();
