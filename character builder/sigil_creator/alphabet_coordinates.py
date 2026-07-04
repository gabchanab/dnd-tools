import numpy as np
import matplotlib.pyplot as plt


def normalize_angle(angle):
    """
    Normalize an angle in radians to the range [-pi, pi].
    """
    return (angle + np.pi) % (2 * np.pi) - np.pi

# Dictionary correlating groups of letters to coordinate points
alphabet_groups = {
    'A-L': (7, [normalize_angle((np.pi/2)-n*(np.pi/6)) for n in range(12)]),
    'M-S': (5, [normalize_angle((np.pi/2)+m*(2*np.pi/7)) for m in range(7)]),
    'T-W': (3, [normalize_angle((np.pi/2)-p*(np.pi/2)) for p in range(4)]),
    'X-Z': (1, [normalize_angle((np.pi/2)+q*(2*np.pi/3)) for q in range(3)]),
}

# Create dictionary for individual letters
# print(np.angle(complex(0, -1)))
# print(alphabet_groups)


def get_coordinate(letter, groups):
    """
    Takes a letter and a dictionary of groups (e.g., {'A-L': (12, [angles]), ...}),
    and returns the specific angle coordinate for that letter within its group.
    """
    letter = letter.upper()
    for group, (count, angles) in groups.items():
        start, end = group.split('-')
        if start <= letter <= end:
            # Find the index of the letter in the group
            index = ord(letter) - ord(start)
            if 0 <= index < len(angles):
                return angles[index]
            else:
                return None
    return None  # Letter not in any group

# Example usage
# print("Coordinate for 'R':", get_coordinate('R', alphabet_groups))

# Create full coordinates dictionary
letter_coords = {}
letter_to_group = {}
for group, (radius, angles) in alphabet_groups.items():
    start, end = group.split('-')
    for i, letter_code in enumerate(range(ord(start), ord(end) + 1)):
        letter = chr(letter_code)
        angle = angles[i]
        letter_coords[letter] = (radius, angle)
        letter_to_group[letter] = group


def _get_letter_points(word):
    word_text = str(word).upper()
    letters = [ch for ch in word_text if ch.isalpha()]
    pts = []
    for ch in letters:
        if ch in letter_coords:
            r, theta = letter_coords[ch]
            pts.append({'ch': ch, 'theta': theta, 'r': r, 'group': letter_to_group.get(ch)})
    return pts


def _normalize_radii(rs, normalize=True, scale_min_frac=0.2, scale_max_frac=0.9):
    if not normalize:
        return list(rs)
    R = max(radius for radius, _ in alphabet_groups.values())
    minr, maxr = min(rs), max(rs)
    if maxr == minr:
        mid_frac = (scale_min_frac + scale_max_frac) / 2.0
        return [mid_frac * R] * len(rs)
    scale_min = scale_min_frac * R
    scale_max = scale_max_frac * R
    span = maxr - minr
    return [((r - minr) / span) * (scale_max - scale_min) + scale_min for r in rs]


def draw_spell_sigil(ax, word, line_color='k', connection='straight', markersize=6,
                     close=False, normalize=True, scale_min_frac=0.2, scale_max_frac=0.9):
    pts = _get_letter_points(word)
    if not pts:
        return

    thetas = [p['theta'] for p in pts]
    rs = [p['r'] for p in pts]
    rs_mapped = _normalize_radii(rs, normalize=normalize,
                                scale_min_frac=scale_min_frac,
                                scale_max_frac=scale_max_frac)

    ax.set_facecolor('white')
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    ax.spines['polar'].set_visible(False)

    ax.plot(thetas, rs_mapped, 'o', color=line_color, markersize=markersize)

    def _draw_segment(t0, r0, g0, t1, r1, g1):
        if connection == 'straight':
            ax.plot([t0, t1], [r0, r1], '-', color=line_color, linewidth=1.5)
        elif connection == 'arc':
            r_arc = (r0 + r1) / 2.0
            u = np.unwrap([t0, t1])
            thetas_arc = np.linspace(u[0], u[1], 80)
            ax.plot(thetas_arc, np.full_like(thetas_arc, r_arc), '-', color=line_color, linewidth=1.5)
        elif connection == 'both':
            if g0 is not None and g0 == g1:
                r_arc = (r0 + r1) / 2.0
                u = np.unwrap([t0, t1])
                thetas_arc = np.linspace(u[0], u[1], 80)
                ax.plot(thetas_arc, np.full_like(thetas_arc, r_arc), '-', color=line_color, linewidth=1.5)
            else:
                ax.plot([t0, t1], [r0, r1], '-', color=line_color, linewidth=1.5)
        else:
            raise ValueError("connection must be 'straight', 'arc', or 'both'")

    for i in range(len(rs_mapped) - 1):
        _draw_segment(thetas[i], rs_mapped[i], pts[i]['group'],
                      thetas[i + 1], rs_mapped[i + 1], pts[i + 1]['group'])
    if close and len(rs_mapped) >= 2:
        _draw_segment(thetas[-1], rs_mapped[-1], pts[-1]['group'],
                      thetas[0], rs_mapped[0], pts[0]['group'])


# Plotting
def plot_word(word, plot_constellation=True, filename='alphabet_polar_plot.png', color='k', markersize=4,
              connect=True, close=False, normalize=True,
              scale_min_frac=0.2, scale_max_frac=0.9):
    """
    Plot only the points corresponding to letters in `word` and save to `filename`.
    If connect=True, draw lines/curves between consecutive letters.
    If close=True, connect the last point back to the first.

    If normalize=True, radial distances are linearly rescaled so the set of
    points occupies the radial range [scale_min_frac*R, scale_max_frac*R].
    Curves (circular arcs) are used when two consecutive letters belong to
    the same group in `alphabet_groups`.
    """
    letters = [ch.upper() for ch in word if ch.isalpha()]
    pts = []
    for ch in letters:
        if ch in letter_coords:
            r, theta = letter_coords[ch]
            grp = letter_to_group.get(ch)
            pts.append({'ch': ch, 'theta': theta, 'r': r, 'group': grp})

    if not pts:
        print("No valid letters to plot.")
        return

    thetas = [p['theta'] for p in pts]
    rs = [p['r'] for p in pts]

    # Optionally normalize radial distances to fill the plotting area
    if normalize:
        R = max(radius for radius, _ in alphabet_groups.values())
        minr, maxr = min(rs), max(rs)
        if maxr == minr:
            mid_frac = (scale_min_frac + scale_max_frac) / 2.0
            rs_mapped = [mid_frac * R] * len(rs)
        else:
            scale_min = scale_min_frac * R
            scale_max = scale_max_frac * R
            span = maxr - minr
            rs_mapped = [((r - minr) / span) * (scale_max - scale_min) + scale_min for r in rs]
    else:
        rs_mapped = list(rs)

    fig = plt.figure()
    ax = fig.add_subplot(111, polar=True)
    if plot_constellation == False:
        ax.set_title(f'Spell Sigil for: {word}', y=1.03)
    else:
        ax.set_title(f'Constellation Sigil for: {word}', y=1.03)

    # draw points (using mapped radii)
    # draw points (using mapped radii); make only the last point a white-filled circle with colored edge
    for i, (theta, r_m) in enumerate(zip(thetas, rs_mapped)):
        if plot_constellation:
            if i == 0:
                ax.plot(theta, r_m, marker='o', markersize=2*markersize,
                        markeredgecolor=color, markerfacecolor=color, linestyle='',
                        zorder=3)
            if i == len(rs_mapped) - 1:
                ax.plot(theta, r_m, marker='o', markersize=2*markersize,
                        markeredgecolor=color, markerfacecolor='white', linestyle='',
                        zorder=3)
        ax.plot(theta, r_m, marker='o', markersize=markersize,
                markeredgecolor=color, markerfacecolor=color, linestyle='',
                zorder=2)

    # draw connecting lines or arcs between consecutive points
    if connect and len(rs_mapped) >= 2:
        def _draw_segment(t0, r0, g0, t1, r1, g1):
            if g0 is not None and g0 == g1:
                # draw circular arc at (approx.) the common radius
                r_arc = (r0 + r1) / 2.0
                u = np.unwrap([t0, t1])
                thetas_arc = np.linspace(u[0], u[1], 100)
                ax.plot(thetas_arc, np.full_like(thetas_arc, r_arc), '-', color=color, linewidth=1)
            else:
                ax.plot([t0, t1], [r0, r1], '-', color=color, linewidth=1)

        for i in range(len(rs_mapped) - 1):
            _draw_segment(thetas[i], rs_mapped[i], pts[i]['group'],
                          thetas[i+1], rs_mapped[i+1], pts[i+1]['group'])

        if close:
            _draw_segment(thetas[-1], rs_mapped[-1], pts[-1]['group'],
                          thetas[0], rs_mapped[0], pts[0]['group'])

    # remove all gridlines and the polar frame
    ax.grid(False)
    ax.xaxis.grid(False)
    ax.yaxis.grid(False)
    ax.spines['polar'].set_visible(False)

    ax.set_xticklabels([])
    ax.set_yticklabels([])

    plt.tight_layout(rect=[0, 0, 1, 0.92])
    plt.savefig(filename, bbox_inches='tight')
    print(f"Plot saved as '{filename}'")



 

def plot_word_with_connection(word, filename='alphabet_connection.png',
                              connection='straight', line_color='k',
                              plot_constellation=False, markersize=4, line_width=1, close=False,
                              normalize=True, scale_min_frac=0.2, scale_max_frac=0.9,
                              title=None, show_title=True):
    """
    Plot one or more words on the same polar figure.

    If `word` is a string, this behaves like the previous version.
    If `word` is a list/tuple of dicts, each dict can contain:
      'word' (required),
      'connection' ('straight', 'arc', or 'both', default 'straight'),
      'line_color' (default 'k'),
      'plot_constellation' (default False),
      'markersize' (default 4),
      'close' (default False),
      'line_width' (default 1).
    """
    def _build_points(raw_word):
        letters = [ch.upper() for ch in raw_word if ch.isalpha()]
        pts = []
        for ch in letters:
            if ch in letter_coords:
                r, theta = letter_coords[ch]
                grp = letter_to_group.get(ch)
                pts.append({'ch': ch, 'theta': theta, 'r': r, 'group': grp})
        return pts

    def _normalize_radii(rs):
        if not normalize:
            return list(rs)
        R = max(radius for radius, _ in alphabet_groups.values())
        minr, maxr = min(rs), max(rs)
        if maxr == minr:
            mid_frac = (scale_min_frac + scale_max_frac) / 2.0
            return [mid_frac * R] * len(rs)
        scale_min = scale_min_frac * R
        scale_max = scale_max_frac * R
        span = maxr - minr
        return [((r - minr) / span) * (scale_max - scale_min) + scale_min for r in rs]

    def _draw_sequence(ax, cfg, rs_mapped):
        thetas = [p['theta'] for p in cfg['pts']]
        for theta, r_m in zip(thetas, rs_mapped):
            if cfg['plot_constellation']:
                ax.plot(theta, r_m, marker='o', markersize=cfg['markersize'],
                        markeredgecolor=cfg['line_color'], markerfacecolor=cfg['line_color'],
                        linestyle='', zorder=3)
            else:
                ax.plot(theta, r_m, marker='o', markersize=0,
                        color=cfg['line_color'], linestyle='', zorder=3)

        def _draw_connection(t0, r0, g0, t1, r1, g1):
            if cfg['connection'] == 'straight':
                ax.plot([t0, t1], [r0, r1], '-', color=cfg['line_color'], linewidth=cfg['line_width'])
            elif cfg['connection'] == 'arc':
                r_arc = (r0 + r1) / 2.0
                u = np.unwrap([t0, t1])
                thetas_arc = np.linspace(u[0], u[1], 100)
                ax.plot(thetas_arc, np.full_like(thetas_arc, r_arc), '-', color=cfg['line_color'], linewidth=cfg['line_width'])
            elif cfg['connection'] == 'both':
                if g0 is not None and g0 == g1:
                    r_arc = (r0 + r1) / 2.0
                    u = np.unwrap([t0, t1])
                    thetas_arc = np.linspace(u[0], u[1], 100)
                    ax.plot(thetas_arc, np.full_like(thetas_arc, r_arc), '-', color=cfg['line_color'], linewidth=cfg['line_width'])
                else:
                    ax.plot([t0, t1], [r0, r1], '-', color=cfg['line_color'], linewidth=cfg['line_width'])
            else:
                raise ValueError("connection must be 'straight', 'arc', or 'both'")

        if len(rs_mapped) >= 2:
            for i in range(len(rs_mapped) - 1):
                _draw_connection(thetas[i], rs_mapped[i], cfg['pts'][i]['group'],
                                 thetas[i + 1], rs_mapped[i + 1], cfg['pts'][i + 1]['group'])
            if cfg['close']:
                _draw_connection(thetas[-1], rs_mapped[-1], cfg['pts'][-1]['group'],
                                 thetas[0], rs_mapped[0], cfg['pts'][0]['group'])

    if isinstance(word, (list, tuple)):
        configs = []
        for item in word:
            if not isinstance(item, dict):
                raise TypeError('Each item in the word list must be a dict')
            raw_word = item.get('word', '')
            pts = _build_points(raw_word)
            if not pts:
                continue
            configs.append({
                'word': raw_word,
                'pts': pts,
                'connection': item.get('connection', 'straight'),
                'line_color': item.get('line_color', 'k'),
                'plot_constellation': item.get('plot_constellation', False),
                'markersize': item.get('markersize', 4),
                'close': item.get('close', False),
                'line_width': item.get('line_width', 1),
            })
        if not configs:
            print("No valid words to plot.")
            return
        all_rs = [p['r'] for cfg in configs for p in cfg['pts']]
        rs_mapped_all = _normalize_radii(all_rs)
        fig = plt.figure()
        fig.patch.set_facecolor('white')
        ax = fig.add_subplot(111, polar=True)
        ax.set_facecolor('white')
        if show_title:
            ax.set_title(title or 'Multiple Words', y=1.03)
            ax.title.set_color('black')
        idx = 0
        for cfg in configs:
            n = len(cfg['pts'])
            rs_mapped = rs_mapped_all[idx:idx + n]
            idx += n
            _draw_sequence(ax, cfg, rs_mapped)
    else:
        pts = _build_points(word)
        if not pts:
            print("No valid letters to plot.")
            return
        cfg = {
            'word': word,
            'pts': pts,
            'connection': connection,
            'line_color': line_color,
            'plot_constellation': plot_constellation,
            'markersize': markersize,
            'close': close,
            'line_width': line_width,
        }
        all_rs = [p['r'] for p in pts]
        rs_mapped_all = _normalize_radii(all_rs)
        fig = plt.figure()
        fig.patch.set_facecolor('white')
        ax = fig.add_subplot(111, polar=True)
        ax.set_facecolor('white')
        if show_title:
            ax.set_title(title or ('Constellation' if plot_constellation else 'Spell Sigil') + f' for: {word}', y=1.03)
            ax.title.set_color('black')
        _draw_sequence(ax, cfg, rs_mapped_all)

    # remove all gridlines and the polar frame
    ax.grid(False)
    ax.xaxis.grid(False)
    ax.yaxis.grid(False)
    ax.spines['polar'].set_visible(False)
    ax.set_xticklabels([])
    ax.set_yticklabels([])

    plt.tight_layout(rect=[0, 0, 1, 1.0 if not show_title else 0.92])
    plt.savefig(filename, bbox_inches='tight')
    print(f"Plot saved as '{filename}'")
 
""" 
Example: plot multiple independent words on the same figure
plot_word_with_connection([
    {'word': 'ABC', 'connection': 'straight', 'line_color': 'red', 'markersize': 4, 'line_width': 1},
    {'word': 'XYZ', 'connection': 'arc', 'line_color': (0.0, 0.5, 0.8), 'plot_constellation': True, 'line_width': 2},
    {'word': 'DEF', 'connection': 'both', 'line_color': 'green', 'line_width': 1},
], filename='multi_words.png', title='Multiple Word Connections')
"""
# plot_word("COUNTERSPELL", plot_constellation=False, filename='spell_sigil.png', color=(0,0.5,0.5), close=True, normalize=False)

if __name__ == '__main__':
    spell_schools = {
        'ABJURATION': [(1.0, 0.0, 0.0), ['KAF','straight'], ['CAH','straight'], ['TUVW','arc']],
        'CONJURATION': [(0.0, 1.0, 1.0), ['MQNROSPM','straight']],
        'DIVINATION': [(1.0, 1.0, 1.0), ['AEI','straight'], ['KCG', 'straight']],
        'ENCHANTMENT': [(0.5, 0.0, 0.5), ['AGI', 'arc'], ['TUVW','arc'], ['XYZ','arc'], ['CXE','straight'], ['KXI','straight'], ['PXQ','straight']],
        'EVOCATION': [(1.0, 0.5, 0.0), ['AEI','straight'], ['TIE','straight'], ['UJL','straight'], ['WDB','straight']],
        'ILLUSION': [(0.0, 0.0, 1.0), ['TVD','straight'], ['WUA','straight'], ['TVJ','straight'], ['WUG','straight']],
        'NECROMANCY': [(1.0, 0.0, 1.0), ['AJGD','straight'], ['PMQ','straight'], ['LBG','straight']],
        'TRANSMUTATION': [(0.0, 0.5, 0.0), ['MQN','arc'], ['NPSQN','straight']],
    }

    sc = 'CONJURATION' # change this to plot different schools of magic
    sp = 'GOODBERRY' # change this to plot different spells
    ti = sp + " Sigil"

    plot_word("HELIOSIS")

    # plot_word_with_connection(
        # [{'word': spell_schools[sc][x][0], 'connection': spell_schools[sc][x][1], 'line_color': spell_schools[sc][0], 'close': True}
        # for x in range(1, len(spell_schools[sc]))] +
        # [{'word': sp, 'connection': 'both', 'line_color': (0.827,0.686, 0.216), 'line_width': 2.5}],
        # filename='spell_sigil.png', title=ti,
        # normalize=False, scale_min_frac=0.3, scale_max_frac=0.8)




# # Basic plot of all letters

# fig = plt.figure()
# ax = fig.add_subplot(111, polar=True)
# for letter, (r, theta) in letter_coords.items():
#     ax.plot(theta, r, 'o', markersize=8, color='C0')  # same color, no label
# # ax.set_title('Alphabet Coordinates in Polar Plot')

# # remove all gridlines and the polar frame
# ax.grid(False)
# ax.xaxis.grid(False)
# ax.yaxis.grid(False)
# ax.spines['polar'].set_visible(False)
# # legend removed to keep only the points visible
# ax.set_xticklabels([])
# ax.set_yticklabels([])

# plt.tight_layout()
# plt.savefig('alphabet_polar_plot.png')
# print("Plot saved as 'alphabet_polar_plot.png'")

# def plot_points(word, filename='alphabet_polar_plot.png', color='k', markersize=6):
#     """
#     Plot only the points corresponding to letters in `word` and save to `filename`.
#     Non-alphabet characters are ignored; unknown letters are skipped.
#     """
#     letters = [ch.upper() for ch in word if ch.isalpha()]
#     fig = plt.figure()
#     ax = fig.add_subplot(111, polar=True)
#     for ch in letters:
#         if ch in letter_coords:
#             r, theta = letter_coords[ch]
#             ax.plot(theta, r, 'o', markersize=markersize, color=color)

#     ax.set_title(f'Constellation Sigil for: {word}')

#     # remove all gridlines and the polar frame
#     ax.grid(False)
#     ax.xaxis.grid(False)
#     ax.yaxis.grid(False)
#     ax.spines['polar'].set_visible(False)

#     ax.set_xticklabels([])
#     ax.set_yticklabels([])

#     plt.tight_layout()
#     plt.savefig(filename)
#     print(f"Plot saved as '{filename}'")