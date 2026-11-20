<?php

namespace App\Http\Controllers;

use App\Models\Episode;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class EpisodeController extends Controller
{
    /**
     * POST /api/episodes
     * Ingests one behavioural episode from the Python gateway.
     */
    public function store(Request $request): JsonResponse
    {
        $data = $request->validate([
            'event_id'    => ['required', 'uuid'],
            'device_id'   => ['nullable', 'string', 'max:64'],
            'timestamp'   => ['required', 'numeric'],     // unix epoch (float) from time.time()
            'composite_z' => ['required', 'numeric'],
            'window_sec'  => ['required', 'integer', 'min:1'],

            'z_scores'                  => ['required', 'array'],
            'z_scores.transition_rate'  => ['required', 'numeric'],
            'z_scores.dwell_entropy'    => ['required', 'numeric'],
            'z_scores.position_var'     => ['required', 'numeric'],
            'z_scores.activity'         => ['required', 'numeric'],

            'features'                  => ['required', 'array'],
            'features.transition_rate'  => ['required', 'numeric'],
            'features.dwell_entropy'    => ['required', 'numeric'],
            'features.position_var'     => ['required', 'numeric'],
            'features.activity'         => ['required', 'numeric'],
        ]);

        // updateOrCreate keyed on event_id => replaying a queued episode is safe.
        $episode = Episode::updateOrCreate(
            ['event_id' => $data['event_id']],
            [
                'device_id'   => $data['device_id'] ?? 'nano33-01',
                'occurred_at' => now()->createFromTimestamp($data['timestamp']),
                'composite_z' => $data['composite_z'],
                'window_sec'  => $data['window_sec'],

                'z_transition_rate' => $data['z_scores']['transition_rate'],
                'z_dwell_entropy'   => $data['z_scores']['dwell_entropy'],
                'z_position_var'    => $data['z_scores']['position_var'],
                'z_activity'        => $data['z_scores']['activity'],

                'f_transition_rate' => $data['features']['transition_rate'],
                'f_dwell_entropy'   => $data['features']['dwell_entropy'],
                'f_position_var'    => $data['features']['position_var'],
                'f_activity'        => $data['features']['activity'],

                'raw_payload' => $data,
            ]
        );

        return response()->json([
            'status'     => $episode->wasRecentlyCreated ? 'created' : 'updated',
            'id'         => $episode->id,
            'event_id'   => $episode->event_id,
            'severity'   => $episode->severity,
        ], $episode->wasRecentlyCreated ? 201 : 200);
    }

    /** GET /api/episodes - most recent first. */
    public function index(): JsonResponse
    {
        return response()->json(
            Episode::latest('occurred_at')->limit(100)->get()
        );
    }
}