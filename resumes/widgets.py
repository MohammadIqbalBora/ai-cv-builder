from itertools import zip_longest

from django import forms


class AdditionalSectionsWidget(forms.Widget):
    template_name = "resumes/widgets/additional_sections.html"

    def value_omitted_from_data(self, data, files, name):
        # Removing every row intentionally clears an existing CV's sections.
        return False

    def value_from_datadict(self, data, files, name):
        def values(key):
            if hasattr(data, "getlist"):
                return data.getlist(key)
            value = data.get(key, [])
            return [value] if isinstance(value, str) else value

        return [
            {"title": title.strip(), "content": content.strip()}
            for title, content in zip_longest(values(name + "_title"), values(name + "_content"), fillvalue="")
            if title.strip() or content.strip()
        ]

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["sections"] = value or [{"title": "", "content": ""}]
        return context
