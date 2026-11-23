(() => {
  const description = document.querySelector("#description");
  const counter = document.querySelector('[data-counter-for="description"]');
  const imageInput = document.querySelector("#image");
  const imageName = document.querySelector("#image_name");
  const form = document.querySelector("form");

  if (description && counter) {
    const updateCounter = () => {
      counter.textContent = `${description.value.length} / ${description.maxLength}`;
    };
    description.addEventListener("input", updateCounter);
    updateCounter();
  }

  if (imageInput && imageName) {
    imageInput.addEventListener("change", () => {
      imageName.textContent = imageInput.files[0]?.name ?? "";
    });
  }

  if (form) {
    form.addEventListener("submit", (event) => {
      if (!form.reportValidity()) {
        event.preventDefault();
      }
    });
  }
})();