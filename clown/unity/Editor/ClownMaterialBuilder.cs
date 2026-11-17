#if UNITY_EDITOR
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// Sets up the clown model for whichever render pipeline the project uses.
/// Put Clown.fbx, the Textures folder and this Editor folder anywhere under Assets, then run
/// Tools > Clown > Create Materials (Bloody) or (Clean).
/// Built-in: Standard. URP: Universal Render Pipeline/Lit. HDRP: HDRP/Lit with MaskMap.
/// The rig is switched to Humanoid so Mixamo and other humanoid animations retarget onto it.
/// </summary>
public static class ClownMaterialBuilder
{
    static readonly string[] Parts =
    {
        "Head", "Body", "Top", "Pants", "Ruff", "Cuff_L", "Cuff_R", "Boot_L", "Boot_R", "Hair",
        "Pompom_0", "Pompom_1", "Pompom_2", "Eye_L", "Eye_R", "Nails", "Axe_Handle", "Axe_Head"
    };

    [MenuItem("Tools/Clown/Create Materials (Bloody)")]
    static void Bloody() => Build(false);

    [MenuItem("Tools/Clown/Create Materials (Clean)")]
    static void Clean() => Build(true);

    enum Pipeline { BuiltIn, URP, HDRP }

    static Pipeline Detect()
    {
        var rp = GraphicsSettings.currentRenderPipeline;
        if (rp == null) return Pipeline.BuiltIn;
        return rp.GetType().Name.Contains("HDRenderPipeline") ? Pipeline.HDRP : Pipeline.URP;
    }

    static void Build(bool clean)
    {
        string[] hits = AssetDatabase.FindAssets("Head_BaseColor t:Texture2D");
        if (hits.Length == 0)
        {
            EditorUtility.DisplayDialog("Clown", "Textures not found. Import the Textures folder from the clown package first.", "OK");
            return;
        }
        string texDir = Path.GetDirectoryName(AssetDatabase.GUIDToAssetPath(hits[0])).Replace('\\', '/');
        string root = Path.GetDirectoryName(texDir).Replace('\\', '/');
        string matDir = root + "/Materials";
        if (!AssetDatabase.IsValidFolder(matDir)) AssetDatabase.CreateFolder(root, "Materials");

        Pipeline pipe = Detect();
        string skin = clean ? "_Clean" : "";
        string fbxPath = null;
        foreach (string g in AssetDatabase.FindAssets("Clown t:Model"))
        {
            string p = AssetDatabase.GUIDToAssetPath(g);
            if (p.EndsWith("Clown.fbx")) { fbxPath = p; break; }
        }
        var importer = fbxPath != null ? (ModelImporter)AssetImporter.GetAtPath(fbxPath) : null;

        foreach (string part in Parts)
        {
            Texture2D albedo = Load(texDir, $"{part}_BaseColor{skin}", false, false);
            if (albedo == null) continue;
            Texture2D normal = Load(texDir, $"{part}_Normal", true, false);
            Texture2D occl = Load(texDir, $"{part}_Occlusion", false, true);
            Texture2D metal = Load(texDir, $"{part}_MetallicSmoothness{skin}", false, true);
            Texture2D mask = Load(texDir, $"{part}_MaskMap{skin}", false, true);

            Material m = NewMaterial(pipe);
            switch (pipe)
            {
                case Pipeline.BuiltIn:
                    m.SetTexture("_MainTex", albedo);
                    m.SetTexture("_BumpMap", normal); m.EnableKeyword("_NORMALMAP");
                    m.SetTexture("_MetallicGlossMap", metal); m.EnableKeyword("_METALLICGLOSSMAP");
                    m.SetFloat("_GlossMapScale", 1f); m.SetFloat("_SmoothnessTextureChannel", 0f);
                    m.SetTexture("_OcclusionMap", occl);
                    break;
                case Pipeline.URP:
                    m.SetTexture("_BaseMap", albedo);
                    m.SetTexture("_BumpMap", normal); m.EnableKeyword("_NORMALMAP");
                    m.SetTexture("_MetallicGlossMap", metal); m.EnableKeyword("_METALLICSPECGLOSSMAP");
                    m.SetFloat("_Smoothness", 1f);
                    m.SetTexture("_OcclusionMap", occl); m.EnableKeyword("_OCCLUSIONMAP");
                    break;
                case Pipeline.HDRP:
                    m.SetTexture("_BaseColorMap", albedo);
                    m.SetTexture("_NormalMap", normal); m.EnableKeyword("_NORMALMAP"); m.EnableKeyword("_NORMALMAP_TANGENT_SPACE");
                    m.SetTexture("_MaskMap", mask); m.EnableKeyword("_MASKMAP");
                    m.SetFloat("_MetallicRemapMax", 1f); m.SetFloat("_SmoothnessRemapMax", 1f); m.SetFloat("_AORemapMax", 1f);
                    break;
            }
            if (part.StartsWith("Eye"))
            {
                m.EnableKeyword("_EMISSION");
                m.SetColor(pipe == Pipeline.HDRP ? "_EmissiveColor" : "_EmissionColor", new Color(0.35f, 0.25f, 0.05f));
            }
            string path = $"{matDir}/Clown_{part}{skin}.mat";
            AssetDatabase.DeleteAsset(path);
            AssetDatabase.CreateAsset(m, path);
            importer?.AddRemap(new AssetImporter.SourceAssetIdentifier(typeof(Material), $"{part}_Game"), m);
        }

        if (importer != null)
        {
            importer.animationType = ModelImporterAnimationType.Human;
            importer.avatarSetup = ModelImporterAvatarSetup.CreateFromThisModel;
            importer.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;
            importer.SaveAndReimport();
        }
        AssetDatabase.SaveAssets();
        Debug.Log($"Clown: {(clean ? "clean" : "bloody")} materials created for {pipe} in {matDir}" +
                  (importer == null ? " (Clown.fbx not found, assign the materials by hand)" : ""));
    }

    static Material NewMaterial(Pipeline p)
    {
        string name = p == Pipeline.BuiltIn ? "Standard" : p == Pipeline.URP ? "Universal Render Pipeline/Lit" : "HDRP/Lit";
        Shader s = Shader.Find(name);
        if (s == null) throw new System.Exception($"Shader '{name}' not found in this project.");
        return new Material(s);
    }

    static Texture2D Load(string dir, string name, bool normalMap, bool linear)
    {
        string path = $"{dir}/{name}.png";
        var ti = AssetImporter.GetAtPath(path) as TextureImporter;
        if (ti == null) return null;
        bool dirty = false;
        if (normalMap && ti.textureType != TextureImporterType.NormalMap) { ti.textureType = TextureImporterType.NormalMap; dirty = true; }
        if (linear && ti.sRGBTexture) { ti.sRGBTexture = false; dirty = true; }
        if (dirty) ti.SaveAndReimport();
        return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
    }
}
#endif
