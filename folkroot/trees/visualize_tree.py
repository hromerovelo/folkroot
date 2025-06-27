"""
BSD 2-Clause License

Copyright (c) 2025, Hilda Romero-Velo
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice, this
  list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

"""
  Created by Hilda Romero-Velo on March 2025.
"""

"""
  ETE3 visualization for phylogenetic trees with database integration.
  This script visualizes NEXUS trees with nodes colored by genre or dataset.
"""

import os
import sys
import dendropy
import argparse
import subprocess
from tempfile import NamedTemporaryFile
from ete3 import Tree, NodeStyle, TextFace, faces
from trees_utils import connect_database
from visualization_utils.visualization_utils import (
    get_colored_genres,
    get_genre_dataset_mapping,
    get_score_metadata,
    lighten_hex_color,
    extract_short_name,
    is_genre_tree,
    create_tree_style,
    DATASET_COLORS,
)


def layout_node(node, color, label_text, extra_info=None):
    """
    Basic node layout with color, label and extra info.

    Args:
        node (ete3.Node): Node to style.
        color (str): Hex color for node.
        label_text (str): Text to display on node.
        extra_info (str): Additional text to display.
    """
    nstyle = NodeStyle()

    nstyle["hz_line_color"] = color
    nstyle["fgcolor"] = color
    nstyle["size"] = 16
    nstyle["vt_line_width"] = 3
    nstyle["hz_line_width"] = 3
    nstyle["bgcolor"] = lighten_hex_color(color, 0.6)

    if node.is_leaf():
        label_face = TextFace(f" {label_text}", fsize=16, bold=True)
        label_face.margin_bottom = 5
        node.add_face(
            label_face,
            column=0,
            position="branch-right",
        )

        if extra_info:
            extra_face = TextFace(f"  ({extra_info})", fsize=14, fgcolor="#505050")
            extra_face.margin_bottom = 5
            node.add_face(
                extra_face,
                column=1,
                position="branch-right",
            )
    node.set_style(nstyle)


def layout_genre_tree(node, genre_dataset_map, dataset_colors):
    """
    Assign colors and labels to nodes in genre trees by dataset.

    Args:
        node (ete3.Node): Node to style.
        genre_dataset_map (dict): Mapping of genres to datasets.
        dataset_colors (dict): Colors for each dataset.
    """
    if node.is_leaf():
        genre = node.name.strip("'\"")
        dataset = genre_dataset_map.get(genre.lower(), "unknown")
        color = dataset_colors.get(dataset, "#a0a0a0")
        layout_node(node, color, genre, dataset)


def layout_score_tree_by_genre(node, conn, genre_colors):
    """
    Assign colors and labels to nodes in score trees by genre.

    Args:
        node (ete3.Node): Node to style.
        conn (sqlite3.Connection): Database connection.
        genre_colors (dict): Colors for each genre.
    """
    if node.is_leaf():
        genre, _ = get_score_metadata(conn, node.name)
        color = genre_colors.get(genre, "#a0a0a0")

        try:
            short_name = extract_short_name(node.name)
            layout_node(node, color, short_name, genre)
        except Exception as e:
            print(f"Error processing node name {node.name}: {e}")
            layout_node(node, color, node.name)


def layout_score_tree_by_dataset(node, conn, dataset_colors):
    """
    Assign colors and labels to nodes in score trees by dataset.

    Args:
        node (ete3.Node): Node to style.
        conn (sqlite3.Connection): Database connection.
        dataset_colors (dict): Colors for each dataset.
    """
    if node.is_leaf():
        _, dataset = get_score_metadata(conn, node.name)
        color = dataset_colors.get(dataset, "#a0a0a0")

        try:
            short_name = extract_short_name(node.name)
            layout_node(node, color, short_name, dataset)
        except Exception as e:
            print(f"Error processing node name {node.name}: {e}")
            layout_node(node, color, node.name)


def add_legend(tree_style, colors_dict, title):
    """
    Add a legend to the tree style.

    Args:
        tree_style (ete3.TreeStyle): Tree style to add legend to.
        colors_dict (dict): Mapping of items to colors.
        title (str): Title for the legend.
    """
    # Title
    legend_header = TextFace(f"  {title}  ", fsize=12, bold=True)
    legend_header.margin_top = 10
    legend_header.margin_bottom = 5
    legend_header.background.color = "#f0f0f0"
    tree_style.legend.add_face(legend_header, column=0)

    # Filter and sort items
    filtered_colors = {k: v for k, v in colors_dict.items() if k != "unknown"}
    items = sorted(
        (name.capitalize(), color) for name, color in filtered_colors.items()
    )

    spacer = TextFace("  ")
    tree_style.legend.add_face(spacer, column=0)

    # Add items to legend
    for name, color in items:
        rect = faces.RectFace(16, 16, color, color)
        tree_style.legend.add_face(rect, column=0)

        text = TextFace(f" {name}    ", fsize=10)
        tree_style.legend.add_face(text, column=0)


def visualize_tree(tree_file, output_file, db_path, by_genre=True, show_gui=False):
    """
    Visualize a phylogenetic tree with genre or dataset colors. Save as image.

    Args:
        tree_file (str): Path to NEXUS tree file.
        output_file (str): Path to save output image.
        db_path (str): Path to SQLite database.
        by_genre (bool): Color by genre instead of dataset.
        show_gui (bool): Show interactive GUI window.
    """
    conn = connect_database(db_path)

    genre_colors = get_colored_genres(conn)
    genre_dataset_map = get_genre_dataset_mapping(conn)
    genre_tree = is_genre_tree(tree_file)

    tree_name = (
        os.path.basename(tree_file)
        .replace("_phylogenetic_tree.nexus", "")
        .replace(".nexus", "")
    )

    try:
        with NamedTemporaryFile(suffix=".nw", delete=False) as temp_file:
            temp_newick = temp_file.name

        try:
            tree_dendro = dendropy.Tree.get(
                path=tree_file,
                schema="nexus",
                preserve_underscores=True,
                suppress_internal_node_taxa=False,
                suppress_leaf_node_taxa=False,
            )
            tree_dendro.write(path=temp_newick, schema="newick")
        except ImportError:
            cmd = f"python3 -c \"import dendropy; tree = dendropy.Tree.get(path='{tree_file}', schema='nexus'); tree.write(path='{temp_newick}', schema='newick')\""
            subprocess.call(cmd, shell=True)

        tree = Tree(temp_newick, format=1)
        os.unlink(temp_newick)
        for node in tree.traverse():
            node.dist = 1
    except Exception as e:
        print(f"Error loading tree from {tree_file}: {e}")
        sys.exit(1)

    # Create tree style
    ts = create_tree_style(tree_name)

    # Apply layout based on tree type
    if genre_tree:
        for node in tree.traverse():
            layout_genre_tree(node, genre_dataset_map, DATASET_COLORS)
        add_legend(ts, DATASET_COLORS, "Datasets")
    else:
        if by_genre:
            for node in tree.traverse():
                layout_score_tree_by_genre(node, conn, genre_colors)
            add_legend(ts, genre_colors, "Genres")
        else:
            for node in tree.traverse():
                layout_score_tree_by_dataset(node, conn, DATASET_COLORS)
            add_legend(ts, DATASET_COLORS, "Datasets")

    conn.close()

    # Show tree in GUI if requested
    if show_gui:
        tree.show(tree_style=ts)

    # Save tree image if output file specified
    if output_file:
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Calculate dimensions based on tree size
        leaf_count = len(tree.get_leaves())
        width = 3000
        if leaf_count > 30:
            width += leaf_count * 35

        height = leaf_count * 100
        height = max(1500, height)

        if leaf_count > 50:
            height += 800

        ts.branch_vertical_margin = 15

        # Adjust dimensions for different formats
        dpi = 300
        if output_file.lower().endswith(".pdf"):
            max_pdf_dimension = 14000

            if width > max_pdf_dimension or height > max_pdf_dimension:
                print(
                    f"Warning: PDF dimensions ({width}x{height}) exceed Adobe limits."
                )
                print("Auto-scaling dimensions while preserving aspect ratio...")

                scale = min(max_pdf_dimension / width, max_pdf_dimension / height)
                width = int(width * scale)
                height = int(height * scale)
                print(f"New dimensions: {width}x{height}")

                dpi = int(dpi / scale)
            else:
                width = int(width * 1.2)
                height = int(height * 1.2)
                dpi = 150
        elif output_file.lower().endswith(".svg"):
            dpi = 96

        tree.render(output_file, tree_style=ts, dpi=dpi, w=width, h=height)
        print(f"Tree image saved to: {output_file}")

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Visualize phylogenetic trees with genre/dataset information from database."
    )
    parser.add_argument(
        "--tree", type=str, required=True, help="Path to NEXUS tree file"
    )
    parser.add_argument(
        "--output", type=str, help="Output image file path (PNG, PDF, SVG format)"
    )

    parser.add_argument(
        "--by-dataset", action="store_true", help="Color by dataset instead of genre"
    )
    parser.add_argument(
        "--gui", action="store_true", help="Show tree in interactive GUI window"
    )

    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    args.db = os.path.join(script_dir, "../database/folkroot.db")

    # If no output specified and not showing GUI, use default output path
    if not args.output and not args.gui:
        input_base = os.path.basename(args.tree).replace(".nexus", "")
        output_dir = os.path.dirname(args.tree)
        color_by = "dataset" if args.by_dataset else "genre"
        args.output = os.path.join(output_dir, f"{input_base}_{color_by}.png")

    visualize_tree(
        args.tree, args.output, args.db, by_genre=not args.by_dataset, show_gui=args.gui
    )
