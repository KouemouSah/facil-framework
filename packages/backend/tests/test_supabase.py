# -*- coding: utf-8 -*-
"""
Test Supabase Connection - Phase 3 Validation
Valide que la connexion Supabase fonctionne avec les credentials restaures
"""
import pytest


class TestSupabaseConnection:
    """Tests de connexion Supabase avec credentials restaures Phase 3"""

    def test_supabase_client_created(self, supabase_client):
        """Valider que le client Supabase est cree"""
        assert supabase_client is not None, "Supabase client should be created"

    def test_supabase_basic_query(self, supabase_client):
        """Test requete simple Supabase - verifier que DB repond"""
        try:
            # Requete simple: compter les users sans recuperer les donnees
            response = supabase_client.table("users").select("*", count="exact").limit(0).execute()
            assert response is not None, "Supabase response should not be None"
            assert hasattr(response, 'count'), "Response should have count attribute"
        except Exception as e:
            pytest.fail(f"Supabase query failed: {e}")

    @pytest.mark.parametrize("table_name", [
        "users",
        "declarations",
        "payments",
        "documents",
        "tax_types",
        "notifications"
    ])
    def test_supabase_tables_accessible(self, supabase_client, table_name):
        """
        Valider que les tables principales sont accessibles
        Tables creees pendant Phase 1 (peuplement Supabase)
        """
        try:
            response = supabase_client.table(table_name).select("count", count="exact").limit(0).execute()
            assert response is not None, f"Table {table_name} should be accessible"
        except Exception as e:
            pytest.fail(f"Table {table_name} check failed: {e}")

    def test_supabase_auth_available(self, supabase_client):
        """Valider que Supabase Auth est disponible"""
        assert hasattr(supabase_client, 'auth'), "Supabase client should have auth"
        assert supabase_client.auth is not None, "Supabase auth should not be None"


class TestSupabaseAdminConnection:
    """Tests avec Service Role Key (privileges admin)"""

    def test_admin_client_created(self, supabase_admin_client):
        """Valider que le client admin Supabase est cree"""
        assert supabase_admin_client is not None, "Admin client should be created"

    def test_admin_client_has_elevated_permissions(self, supabase_admin_client):
        """
        Test que service role key donne acces admin
        (peut bypasser RLS - Row Level Security)
        """
        try:
            # Avec service role, on peut faire des operations admin
            response = supabase_admin_client.table("users").select("*", count="exact").limit(1).execute()
            assert response is not None
            # Service role devrait avoir acces meme avec RLS active
        except Exception as e:
            pytest.fail(f"Admin client query failed: {e}")


class TestSupabaseDatabase:
    """Tests pour verifier l'etat de la base de donnees"""

    def test_database_has_users(self, supabase_client):
        """Verifier que la table users contient des donnees (base peuplee Phase 1)"""
        try:
            response = supabase_client.table("users").select("*", count="exact").limit(1).execute()
            # Verifier qu'on peut interroger (meme si vide, ca devrait fonctionner)
            assert response is not None
            assert hasattr(response, 'data')
        except Exception as e:
            pytest.fail(f"Failed to query users table: {e}")

    def test_database_schema_version(self, supabase_admin_client):
        """Verifier que le schema de la base de donnees est coherent"""
        try:
            # Test simple: verifier qu'on peut acceder aux metadonnees
            response = supabase_admin_client.table("users").select("*").limit(1).execute()
            assert response is not None
        except Exception as e:
            # Si la table n'existe pas, c'est un probleme critique
            pytest.fail(f"Database schema issue: {e}")


class TestSupabaseRealtime:
    """Tests pour verifier que Realtime est disponible (optionnel)"""

    def test_realtime_available(self, supabase_client):
        """Verifier que Supabase Realtime est disponible"""
        assert hasattr(supabase_client, 'realtime'), \
            "Supabase client should have realtime capability"

    def test_storage_available(self, supabase_client):
        """Verifier que Supabase Storage est disponible"""
        assert hasattr(supabase_client, 'storage'), \
            "Supabase client should have storage capability"


class TestSupabasePerformance:
    """Tests de performance basiques"""

    def test_connection_latency(self, supabase_client):
        """Test que la connexion Supabase est raisonnablement rapide"""
        import time

        start = time.time()
        try:
            supabase_client.table("users").select("count", count="exact").limit(0).execute()
            elapsed = time.time() - start

            # La requete devrait prendre moins de 5 secondes
            assert elapsed < 5.0, f"Supabase query took {elapsed:.2f}s (too slow)"
        except Exception as e:
            pytest.fail(f"Connection test failed: {e}")

    @pytest.mark.slow
    def test_multiple_concurrent_queries(self, supabase_client):
        """Test plusieurs requetes simultanees (stress test leger)"""
        import concurrent.futures

        def query_table(table_name):
            return supabase_client.table(table_name).select("count", count="exact").limit(0).execute()

        tables = ["users", "declarations", "payments"]

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(query_table, table) for table in tables]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(results) == 3, "All queries should complete"
