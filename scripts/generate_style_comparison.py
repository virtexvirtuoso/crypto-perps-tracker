#!/usr/bin/env python3
"""
Generate style comparison HTML for matplotlib chart styles
Shows actual market data in different visual styles for easy comparison
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import io
import base64
import os
from datetime import datetime
from compare_all_exchanges import fetch_all_enhanced

# Tableau color palette
TABLEAU_COLORS = {
    'blue': '#4E79A7',
    'orange': '#F28E2B',
    'red': '#E15759',
    'teal': '#76B7B2',
    'green': '#59A14F',
    'yellow': '#EDC948',
    'purple': '#B07AA1',
    'pink': '#FF9DA7',
}

# Styles to compare - organized by category
STYLES_TO_TEST = [
    # Current/Recommended
    ('current_enhanced', 'Current Enhanced (Tableau + Rounded)', 'current'),

    # Built-in Dark Styles
    ('dark_background', 'Dark Background (Built-in)', 'builtin'),
    ('seaborn-v0_8-dark', 'Seaborn Dark', 'builtin'),
    ('seaborn-v0_8-darkgrid', 'Seaborn Dark Grid', 'builtin'),
    ('seaborn-v0_8-dark-palette', 'Seaborn Dark Palette', 'builtin'),

    # Professional/Financial Styles
    ('qbstyles_dark', 'QB Styles Dark (Consulting)', 'professional'),
    ('dracula', 'Dracula (matplotx)', 'professional'),

    # Creative Styles
    ('cyberpunk', 'Cyberpunk (Neon Blue)', 'creative'),
    ('cyberpunk_amber', 'Cyberpunk Amber (Subtle Glow)', 'creative'),

    # Classic Light Styles (for comparison)
    ('ggplot', 'GGPlot (R-style)', 'light'),
    ('fivethirtyeight', 'FiveThirtyEight', 'light'),
    ('bmh', 'Bayesian Methods for Hackers', 'light'),
    ('Solarize_Light2', 'Solarize Light', 'light'),
]


def generate_funding_chart_enhanced(exchanges, rates, colors):
    """Generate current enhanced style with rounded corners"""
    fig, ax = plt.subplots(figsize=(12, 6), facecolor='#1e1e1e')
    ax.set_facecolor('#2d2d2d')

    bars = ax.bar(exchanges, rates, color=colors, alpha=0.9, edgecolor='#555555', linewidth=2, zorder=2)

    # Replace with rounded corners
    rounded_bars = []
    for i, bar in enumerate(bars):
        x, y = bar.get_xy()
        width = bar.get_width()
        height = bar.get_height()
        bar.remove()

        rounded_bar = FancyBboxPatch(
            (x, y if height >= 0 else y + height),
            width, abs(height),
            boxstyle="round,pad=0.008,rounding_size=0.03",
            facecolor=colors[i],
            edgecolor='#666666',
            linewidth=2,
            alpha=0.95,
            zorder=2
        )
        ax.add_patch(rounded_bar)
        rounded_bars.append(rounded_bar)

    # Add labels
    for i, (bar, rate) in enumerate(zip(rounded_bars, rates)):
        bbox = bar.get_bbox()
        x_pos = bbox.x0 + bbox.width / 2
        y_pos = bbox.y1 if rate >= 0 else bbox.y0

        ax.text(x_pos, y_pos, f'{rate:.4f}%',
                ha='center', va='bottom' if rate >= 0 else 'top',
                fontsize=11, fontweight='bold', color='white',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#1e1e1e', edgecolor='none', alpha=0.7))

    ax.set_xlabel('Exchange', fontsize=14, fontweight='bold', color='white', labelpad=10)
    ax.set_ylabel('Funding Rate (%)', fontsize=14, fontweight='bold', color='white', labelpad=10)
    ax.set_title('BTC Funding Rates by Exchange', fontsize=16, fontweight='bold', pad=20, color='white')
    ax.axhline(y=0, color='#888888', linestyle='-', linewidth=1, alpha=0.8, zorder=1)
    ax.grid(axis='y', alpha=0.15, color='#666666', linewidth=0.5, zorder=0)

    ax.tick_params(axis='x', colors='white', labelsize=11)
    ax.tick_params(axis='y', colors='white', labelsize=11)

    for spine in ax.spines.values():
        spine.set_edgecolor('#444444')
        spine.set_linewidth(1.5)

    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    return fig


def generate_funding_chart_standard(exchanges, rates, colors, style_name):
    """Generate chart with specified matplotlib style"""

    # Handle special third-party libraries
    if style_name == 'qbstyles_dark':
        try:
            from qbstyles import mpl_style
            mpl_style(dark=True)
        except ImportError:
            print(f"   ⚠️  qbstyles not installed, using dark_background instead")
            plt.style.use('dark_background')
    elif style_name == 'cyberpunk':
        try:
            import mplcyberpunk
            plt.style.use("cyberpunk")
        except ImportError:
            print(f"   ⚠️  mplcyberpunk not installed, using dark_background instead")
            plt.style.use('dark_background')
    elif style_name == 'cyberpunk_amber':
        # Custom cyberpunk with amber glow
        try:
            import mplcyberpunk
            plt.style.use("cyberpunk")
        except ImportError:
            print(f"   ⚠️  mplcyberpunk not installed, using dark_background instead")
            plt.style.use('dark_background')
    elif style_name == 'dracula':
        try:
            import matplotx
            plt.style.use(matplotx.styles.dracula)
        except ImportError:
            print(f"   ⚠️  matplotx not installed, using dark_background instead")
            plt.style.use('dark_background')
    elif style_name != 'current_enhanced':
        plt.style.use(style_name)

    fig, ax = plt.subplots(figsize=(12, 6))

    # Determine if dark or light theme
    is_dark = style_name in ['dark_background', 'seaborn-v0_8-dark', 'seaborn-v0_8-darkgrid',
                              'seaborn-v0_8-dark-palette', 'qbstyles_dark', 'cyberpunk', 'cyberpunk_amber', 'dracula']

    # Use style-appropriate colors
    if style_name == 'cyberpunk_amber':
        # Custom amber color palette for cyberpunk
        amber_colors = []
        for rate in rates:
            if rate > 0.01:
                amber_colors.append('#FF6B35')  # Bright amber-red
            elif rate < 0:
                amber_colors.append('#F7931E')  # Bitcoin orange
            else:
                amber_colors.append('#FDB44B')  # Warm amber

        bars = ax.bar(exchanges, rates, color=amber_colors, alpha=0.9, edgecolor='#FFA500', linewidth=1.5)
        text_color = 'white'

        # Add subtle glow effect using mplcyberpunk
        try:
            import mplcyberpunk
            mplcyberpunk.add_glow_effects(ax=ax, n_glow_lines=5, alpha_line=0.15)
        except:
            pass
    elif is_dark:
        # For dark styles, use our Tableau colors
        bars = ax.bar(exchanges, rates, color=colors, alpha=0.85, edgecolor='white', linewidth=1.5)
        text_color = 'white'
    else:
        # For light styles, let the style handle colors
        bars = ax.bar(exchanges, rates, alpha=0.85, edgecolor='black', linewidth=1.5)
        text_color = 'black'

    # Add labels
    for bar, rate in zip(bars, rates):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{rate:.4f}%',
                ha='center', va='bottom' if height > 0 else 'top',
                fontsize=10, fontweight='bold', color=text_color)

    ax.set_xlabel('Exchange', fontsize=12, fontweight='bold')
    ax.set_ylabel('Funding Rate (%)', fontsize=12, fontweight='bold')
    ax.set_title('BTC Funding Rates by Exchange', fontsize=14, fontweight='bold', pad=20)
    ax.axhline(y=0, color='gray', linestyle='-', linewidth=0.8)
    ax.grid(axis='y', alpha=0.3)

    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    return fig


def fig_to_base64(fig):
    """Convert matplotlib figure to base64 string for HTML embedding"""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    img_str = base64.b64encode(buf.read()).decode()
    plt.close(fig)
    return img_str


def generate_comparison_html(results):
    """Generate HTML comparison page"""

    # Fetch actual market data
    print("📊 Fetching live market data...")

    # Filter successful exchanges with funding rates
    exchanges = []
    rates = []
    colors = []

    for r in results:
        if r.get('status') == 'success' and r.get('funding_rate') is not None:
            exchanges.append(r['exchange'])
            rate = r['funding_rate']
            rates.append(rate)

            # Tableau colors
            if rate > 0.01:
                colors.append(TABLEAU_COLORS['red'])
            elif rate < 0:
                colors.append(TABLEAU_COLORS['green'])
            else:
                colors.append(TABLEAU_COLORS['blue'])

    print(f"✅ Loaded data for {len(exchanges)} exchanges")
    print("🎨 Generating charts in different styles...")

    # Generate charts in different styles
    chart_images = {}

    for style_info in STYLES_TO_TEST:
        style_name, style_label, category = style_info
        try:
            print(f"   • {style_label}...")

            if style_name == 'current_enhanced':
                fig = generate_funding_chart_enhanced(exchanges, rates, colors)
            else:
                fig = generate_funding_chart_standard(exchanges, rates, colors, style_name)

            chart_images[style_label] = {
                'image': fig_to_base64(fig),
                'category': category
            }
            plt.style.use('default')  # Reset style

        except Exception as e:
            print(f"   ⚠️  Could not generate {style_label}: {e}")

    # Generate HTML
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Matplotlib Style Comparison - Market Report Charts</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            padding: 20px;
            line-height: 1.6;
        }}

        .header {{
            max-width: 1400px;
            margin: 0 auto 40px;
            text-align: center;
            padding: 40px 20px;
            background: linear-gradient(135deg, #1e2936 0%, #141b24 100%);
            border-radius: 12px;
            border: 1px solid #30363d;
        }}

        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            background: linear-gradient(135deg, #58a6ff 0%, #79c0ff 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}

        .header p {{
            color: #8b949e;
            font-size: 1.1em;
        }}

        .timestamp {{
            color: #6e7681;
            font-size: 0.9em;
            margin-top: 10px;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}

        .style-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(600px, 1fr));
            gap: 30px;
            margin-bottom: 40px;
        }}

        .style-card {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 12px;
            padding: 20px;
            transition: all 0.3s ease;
            cursor: pointer;
        }}

        .style-card:hover {{
            border-color: #58a6ff;
            box-shadow: 0 0 20px rgba(88, 166, 255, 0.3);
            transform: translateY(-2px);
        }}

        .style-card.selected {{
            border-color: #3fb950;
            box-shadow: 0 0 20px rgba(63, 185, 80, 0.4);
        }}

        .style-name {{
            font-size: 1.3em;
            font-weight: 600;
            margin-bottom: 15px;
            color: #58a6ff;
        }}

        .style-card.selected .style-name {{
            color: #3fb950;
        }}

        .chart-image {{
            width: 100%;
            border-radius: 8px;
            background: #0d1117;
        }}

        .select-button {{
            margin-top: 15px;
            padding: 10px 20px;
            background: #238636;
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 1em;
            font-weight: 600;
            cursor: pointer;
            width: 100%;
            transition: background 0.2s;
        }}

        .select-button:hover {{
            background: #2ea043;
        }}

        .style-card.selected .select-button {{
            background: #3fb950;
        }}

        .footer {{
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            color: #6e7681;
            font-size: 0.9em;
        }}

        .badge {{
            display: inline-block;
            padding: 4px 10px;
            background: #1f6feb;
            color: white;
            border-radius: 12px;
            font-size: 0.8em;
            margin-left: 10px;
        }}

        .badge.recommended {{
            background: #238636;
        }}

        @media (max-width: 768px) {{
            .style-grid {{
                grid-template-columns: 1fr;
            }}

            .header h1 {{
                font-size: 1.8em;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Matplotlib Style Comparison</h1>
        <p>Compare different visual styles using actual market data</p>
        <p class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
    </div>

    <div class="container">
"""

    # Organize charts by category
    categories = {
        'current': '🌟 Current Style',
        'builtin': '🎨 Built-in Dark Styles',
        'professional': '💼 Professional/Financial Styles',
        'creative': '✨ Creative Styles',
        'light': '☀️ Light Styles (For Comparison)'
    }

    category_descriptions = {
        'current': 'Your current custom-designed style with all enhancements',
        'builtin': 'Matplotlib\'s native dark mode styles - no installation required',
        'professional': 'Third-party professional themes used in finance and consulting',
        'creative': 'Eye-catching styles with special effects like neon glows',
        'light': 'Light-themed styles for presentations or print materials'
    }

    chart_index = 0
    for cat_key, cat_title in categories.items():
        # Filter charts for this category
        cat_charts = {k: v for k, v in chart_images.items() if v['category'] == cat_key}

        if cat_charts:
            html_content += f"""
        <div style="margin-bottom: 50px;">
            <h2 style="color: #58a6ff; margin-bottom: 10px; font-size: 1.8em;">{cat_title}</h2>
            <p style="color: #8b949e; margin-bottom: 30px; font-size: 1.1em;">{category_descriptions[cat_key]}</p>

            <div class="style-grid">
"""

            for style_label, data in cat_charts.items():
                img_data = data['image']
                is_current = cat_key == 'current'
                badge = '<span class="badge recommended">CURRENT</span>' if is_current else ''

                # Add special badges for certain styles
                if 'Cyberpunk Amber' in style_label:
                    badge += '<span class="badge" style="background: #FF6B35;">CRYPTO THEME</span>'
                    badge += '<span class="badge" style="background: #F7931E;">SUBTLE GLOW</span>'
                elif 'Cyberpunk' in style_label and 'Amber' not in style_label:
                    badge += '<span class="badge" style="background: #9b59b6;">NEON GLOW</span>'
                elif 'QB Styles' in style_label:
                    badge += '<span class="badge" style="background: #e67e22;">CONSULTING</span>'
                elif 'Dracula' in style_label:
                    badge += '<span class="badge" style="background: #e74c3c;">POPULAR</span>'

                html_content += f"""
            <div class="style-card" id="style-{chart_index}">
                <div class="style-name">{style_label}{badge}</div>
                <img src="data:image/png;base64,{img_data}" alt="{style_label}" class="chart-image">
                <button class="select-button" onclick="selectStyle({chart_index}, '{style_label}')">
                    Select This Style
                </button>
            </div>
"""
                chart_index += 1

            html_content += """
            </div>
        </div>
"""

    html_content += """
        </div>
    </div>

    <div class="footer">
        <p style="font-size: 1.1em; margin-bottom: 20px;">💡 <strong>Tip:</strong> Click on any chart to select your preferred style</p>
        <p>Each chart shows the same live market data with different visual styling</p>

        <div style="margin-top: 30px; padding: 20px; background: #161b22; border: 1px solid #30363d; border-radius: 8px; text-align: left;">
            <h3 style="color: #58a6ff; margin-bottom: 15px;">📦 Installation Instructions for Third-Party Styles</h3>

            <p style="margin-bottom: 10px;"><strong>Built-in styles</strong> work immediately - no installation needed!</p>

            <p style="margin-top: 15px; margin-bottom: 10px;"><strong>For Professional/Creative styles:</strong></p>
            <code style="background: #0d1117; padding: 10px; display: block; border-radius: 4px; color: #3fb950; margin-bottom: 5px;">
                pip install qbstyles          # QB Styles Dark (Consulting)<br>
                pip install mplcyberpunk       # Cyberpunk (Neon Glow)<br>
                pip install matplotx           # Dracula and other themes
            </code>

            <p style="margin-top: 20px; color: #8b949e; font-size: 0.9em;">
                💡 Third-party libraries enhance matplotlib with professionally-designed themes used by data scientists, financial analysts, and consultants worldwide.
            </p>
        </div>

        <p style="margin-top: 30px; font-size: 0.85em; color: #6e7681;">
            Generated with live BTC funding rate data from 6 exchanges<br>
            Powered by matplotlib {matplotlib.__version__}
        </p>
    </div>

    <script>
        let selectedStyle = null;

        function selectStyle(index, styleName) {
            // Remove previous selection
            if (selectedStyle !== null) {
                document.getElementById('style-' + selectedStyle).classList.remove('selected');
            }

            // Add new selection
            selectedStyle = index;
            document.getElementById('style-' + index).classList.add('selected');

            console.log('Selected style:', styleName);

            // Show confirmation
            alert('✅ Selected: ' + styleName + '\\n\\nThis style preference has been noted!');
        }

        // Click anywhere on card to select
        document.querySelectorAll('.style-card').forEach((card, index) => {
            card.addEventListener('click', function(e) {
                if (!e.target.classList.contains('select-button')) {
                    this.querySelector('.select-button').click();
                }
            });
        });
    </script>
</body>
</html>
"""

    return html_content


if __name__ == '__main__':
    print("🚀 Generating style comparison page...")
    print()

    # Fetch live data
    results = fetch_all_enhanced()

    # Generate HTML
    html = generate_comparison_html(results)

    # Save to file
    output_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'style_comparison.html')
    with open(output_file, 'w') as f:
        f.write(html)

    print()
    print(f"✅ Style comparison page created: {output_file}")

    # Open in browser (only works on Mac/Linux with display)
    if os.path.exists('/usr/bin/open'):
        print("🌐 Opening in browser...")
        os.system(f'open "{output_file}"')
    else:
        print("💡 Copy this file to your local machine to view in browser")
