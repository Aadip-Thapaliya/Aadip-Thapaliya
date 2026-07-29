# Aadip GitHub Profile README Setup

This folder is ready for your existing special GitHub profile repository:

```text
Aadip-Thapaliya/Aadip-Thapaliya
```

## Files to Upload

Upload these files/folders to the root of your repository:

```text
README.md
assets/dark.svg
assets/light.svg
assets/projects.svg
.github/workflows/snake.yml
Lebenslauf_von_Aadip_Thapaliya.pdf
```

## Exact Changes to Make on GitHub

1. Open your repository:

```text
https://github.com/Aadip-Thapaliya/Aadip-Thapaliya
```

2. Replace your current `README.md` with the new `README.md`.

3. Create a folder called:

```text
assets
```

4. Upload these files inside `assets`:

```text
dark.svg
light.svg
projects.svg
```

5. Upload your new CV to the root of the repo with exactly this filename:

```text
Lebenslauf_von_Aadip_Thapaliya.pdf
```

6. Create this workflow file:

```text
.github/workflows/snake.yml
```

7. Go to:

```text
Actions -> Generate Contribution Snake -> Run workflow
```

8. Wait until it finishes. It will create a new branch called:

```text
output
```

That branch stores:

```text
snake.svg
snake-dark.svg
```

## Important GitHub Setting

If the workflow fails because it cannot push, go to:

```text
Settings -> Actions -> General -> Workflow permissions
```

Select:

```text
Read and write permissions
```

Then run the workflow again.

## What Makes It Move

The moving parts come from SVG animation:

- `assets/dark.svg` and `assets/light.svg` include animated lines and floating shapes.
- `assets/projects.svg` includes small card movement.
- `snake.yml` generates the moving contribution snake automatically.

## Things You Can Edit Later

In `README.md`, you can change:

- LinkedIn URL
- Gmail address
- Project links
- Resume filename
- Skills
- GitHub stats colors

In `assets/dark.svg` and `assets/light.svg`, you can change:

- Main title
- Subtitle
- Focus stack
- Colors
- Animation speed
