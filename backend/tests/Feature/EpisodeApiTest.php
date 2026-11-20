<?php

namespace Tests\Feature;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class EpisodeApiTest extends TestCase
{
    use RefreshDatabase;

    private function payload(array $overrides = []): array
    {
        return array_merge([
            'event_id'    => 'f780c490-7f11-4a4a-8f6d-aff2da5dc142',
            'device_id'   => 'nano33-01',
            'timestamp'   => 1786189508.39,
            'composite_z' => 3.05,
            'window_sec'  => 120,
            'z_scores'    => ['transition_rate' => 1.217, 'dwell_entropy' => 3.707, 'position_var' => 5.062, 'activity' => 2.212],
            'features'    => ['transition_rate' => 8.444, 'dwell_entropy' => 1.46,  'position_var' => 978.178, 'activity' => 8.075],
        ], $overrides);
    }

    public function test_dashboard_renders(): void
    {
        $this->get('/')->assertOk();
    }

    public function test_episode_is_created(): void
    {
        $this->postJson('/api/episodes', $this->payload())
            ->assertCreated()
            ->assertJson(['status' => 'created', 'severity' => 'moderate']);

        $this->assertDatabaseCount('episodes', 1);
    }

    public function test_replaying_same_event_id_is_idempotent(): void
    {
        $this->postJson('/api/episodes', $this->payload())->assertCreated();
        $this->postJson('/api/episodes', $this->payload(['composite_z' => 4.2]))
            ->assertOk()
            ->assertJson(['status' => 'updated', 'severity' => 'high']);

        $this->assertDatabaseCount('episodes', 1);
    }

    public function test_payload_without_event_id_is_rejected(): void
    {
        $p = $this->payload();
        unset($p['event_id']);

        $this->postJson('/api/episodes', $p)->assertUnprocessable();
        $this->assertDatabaseCount('episodes', 0);
    }

    public function test_index_and_export(): void
    {
        $this->postJson('/api/episodes', $this->payload());

        $this->getJson('/api/episodes')->assertOk()->assertJsonCount(1);
        $this->get('/export')->assertOk()->assertHeader('Content-Type', 'text/csv; charset=utf-8');
    }
}
